"""
边缘服务器核心管理器 — 管理类脑盒子与无人机设备
"""
import time
import threading
import logging
from typing import Dict, List, Optional, Any, Callable
from models import (
    BrainBoxNode,
    DroneDevice,
    NavigationTask,
    BrainBoxStatus,
    DeviceStatus,
    NavigationStatus,
)
from config.settings import settings
from .heartbeat import HeartbeatMonitor
from .brain_box_client import BrainBoxClient

logger = logging.getLogger(__name__)


class EdgeManager:
    """
    边缘服务器核心管理器（单例）

    功能:
    - 管理类脑盒子实例 (注册、移除、心跳监控)
    - 管理无人机设备表 (由类脑盒子上报，绑定到对应 brain_box)
    - 转发导航指令到类脑盒子
    - 接收并存储轨迹上报
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        heartbeat_interval: float = 10.0,
        box_timeout: float = 30.0,
        on_box_offline: Optional[Callable[[BrainBoxNode], None]] = None,
    ):
        if hasattr(self, "_initialized"):
            return

        self._lock_internal = threading.RLock()

        self._brain_boxes: Dict[str, BrainBoxNode] = {}
        self._devices: Dict[str, DroneDevice] = {}
        self._tasks: Dict[str, NavigationTask] = {}

        self._client = BrainBoxClient(timeout=settings.request_timeout)

        self._heartbeat = HeartbeatMonitor(
            self,
            check_interval_s=heartbeat_interval,
            box_timeout_s=box_timeout,
        )
        self._heartbeat.start()

        self._on_box_offline = on_box_offline

        self._initialized = True
        logger.info("EdgeManager initialized")

    # ==================================================================
    #  类脑盒子管理
    # ==================================================================

    def add_brain_box(
        self,
        box_id: str,
        ip_address: str,
        port: int = 9000,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """注册类脑盒子"""
        with self._lock_internal:
            if box_id in self._brain_boxes:
                return {"code": -1, "msg": f"类脑盒子 {box_id} 已存在", "data": {}}

            box = BrainBoxNode(
                box_id=box_id,
                ip_address=ip_address,
                port=port,
                metadata=metadata or {},
            )
            self._brain_boxes[box_id] = box
            logger.info("BrainBox added: %s (%s:%d)", box_id, ip_address, port)

            return {"code": 0, "msg": "success", "data": box.to_dict()}

    def remove_brain_box(self, box_id: str) -> Dict[str, Any]:
        """移除类脑盒子并清理其关联的设备"""
        with self._lock_internal:
            if box_id not in self._brain_boxes:
                return {"code": -1, "msg": f"类脑盒子 {box_id} 不存在", "data": {}}

            box = self._brain_boxes.pop(box_id)

            removed_devices = [
                did for did, d in self._devices.items() if d.box_id == box_id
            ]
            for did in removed_devices:
                self._devices.pop(did)

            logger.info(
                "BrainBox removed: %s (cleaned %d devices)",
                box_id,
                len(removed_devices),
            )
            return {"code": 0, "msg": "success", "data": box.to_dict()}

    def list_brain_boxes(self) -> Dict[str, Any]:
        """获取所有类脑盒子列表"""
        with self._lock_internal:
            boxes = list(self._brain_boxes.values())
            return {
                "code": 0,
                "msg": "success",
                "data": {
                    "total": len(boxes),
                    "brain_boxes": [b.to_dict() for b in boxes],
                },
            }

    # ==================================================================
    #  心跳接收（brain_box → edge_server）
    # ==================================================================

    def receive_heartbeat(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        接收类脑盒子心跳

        brain_box 定期调用此接口上报自身状态。
        如果 box_id 尚未注册且提供了 ip/port 信息，则自动注册。
        """
        box_id = params.get("box_id", "")
        with self._lock_internal:
            if box_id in self._brain_boxes:
                box = self._brain_boxes[box_id]
                box.last_heartbeat = time.time()
                box.drone_count = params.get("drone_count", box.drone_count)
                box.online_drone_count = params.get("online_count", box.online_drone_count)
                if box.status == BrainBoxStatus.OFFLINE:
                    box.status = BrainBoxStatus.ONLINE
                    logger.info("BrainBox %s back online", box_id)
                return {"code": 0, "msg": "success", "data": box.to_dict()}

            ip_address = params.get("ip_address", "")
            port = params.get("port", 9000)
            if not ip_address:
                return {
                    "code": -1,
                    "msg": f"类脑盒子 {box_id} 未注册，且心跳中缺少 ip_address",
                    "data": {},
                }

            box = BrainBoxNode(
                box_id=box_id,
                ip_address=ip_address,
                port=port,
                drone_count=params.get("drone_count", 0),
                online_drone_count=params.get("online_count", 0),
            )
            self._brain_boxes[box_id] = box
            logger.info("BrainBox auto-registered from heartbeat: %s", box_id)
            return {"code": 0, "msg": "auto-registered", "data": box.to_dict()}

    # ==================================================================
    #  无人机状态上报（brain_box → edge_server）
    # ==================================================================

    def receive_drone_report(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        接收无人机状态上报

        brain_box 定期/即时上报其管辖的无人机信息。
        """
        box_id = params.get("box_id", "")
        with self._lock_internal:
            if box_id not in self._brain_boxes:
                return {"code": -1, "msg": f"类脑盒子 {box_id} 未注册", "data": {}}

            devices_data = params.get("devices", [])
            event = params.get("event", "")

            if event == "status_change":
                device_data = params.get("device", {})
                if device_data:
                    self._upsert_device(box_id, device_data)
                return {"code": 0, "msg": "status_change received", "data": {}}

            for dev in devices_data:
                self._upsert_device(box_id, dev)

            return {
                "code": 0,
                "msg": "success",
                "data": {"updated_count": len(devices_data)},
            }

    def _upsert_device(self, box_id: str, device_data: Dict[str, Any]) -> None:
        """插入或更新设备记录"""
        device_id = device_data.get("device_id", "")
        if not device_id:
            return

        if device_id in self._devices:
            dev = self._devices[device_id]
            dev.status = DeviceStatus(device_data.get("status", dev.status.value))
            dev.last_heartbeat = device_data.get("last_heartbeat", time.time())
            dev.position = device_data.get("position", dev.position)
            dev.metadata = device_data.get("metadata", dev.metadata)
        else:
            dev = DroneDevice(
                device_id=device_id,
                box_id=box_id,
                device_type=device_data.get("device_type", "quadcopter"),
                protocol=device_data.get("protocol", "mavlink"),
                status=DeviceStatus(device_data.get("status", "online")),
                last_heartbeat=device_data.get("last_heartbeat", time.time()),
                position=device_data.get("position", {}),
                metadata=device_data.get("metadata", {}),
            )
            self._devices[device_id] = dev
            logger.info("Drone registered: %s (box=%s)", device_id, box_id)

    # ==================================================================
    #  轨迹上报（brain_box → edge_server）
    # ==================================================================

    def receive_trajectory_report(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """接收导航轨迹上报"""
        box_id = params.get("box_id", "")
        trajectory = params.get("trajectory", {})

        with self._lock_internal:
            trajectory_id = trajectory.get("trajectory_id", "")
            device_id = trajectory.get("device_id", "")

            matched = False
            for task in self._tasks.values():
                if task.trajectory_id == trajectory_id and task.status == NavigationStatus.EXECUTING:
                    task.result = trajectory
                    matched = True
                    break

            if not matched:
                for task in self._tasks.values():
                    if (
                        task.box_id == box_id
                        and task.device_id == device_id
                        and task.status in (NavigationStatus.PENDING, NavigationStatus.EXECUTING)
                    ):
                        task.trajectory_id = trajectory_id
                        task.status = NavigationStatus.EXECUTING
                        task.result = trajectory
                        matched = True
                        break

            logger.info(
                "Trajectory report received: box=%s trajectory=%s device=%s matched=%s",
                box_id, trajectory_id, device_id, matched,
            )
            return {"code": 0, "msg": "success", "data": {"trajectory_id": trajectory_id}}

    # ==================================================================
    #  设备查询
    # ==================================================================

    def list_devices(self, box_id: str = "all") -> Dict[str, Any]:
        """获取无人机设备列表"""
        with self._lock_internal:
            devices = list(self._devices.values())
            if box_id != "all":
                devices = [d for d in devices if d.box_id == box_id]

            return {
                "code": 0,
                "msg": "success",
                "data": {
                    "total": len(devices),
                    "devices": [d.to_dict() for d in devices],
                },
            }

    def get_device_info(self, device_id: str) -> Optional[Dict[str, Any]]:
        """获取设备详情"""
        with self._lock_internal:
            dev = self._devices.get(device_id)
            if not dev:
                return None
            return dev.to_dict()

    # ==================================================================
    #  转发指令（edge_server → brain_box）
    # ==================================================================

    def forward_scan_drones(self, box_id: str) -> Dict[str, Any]:
        """转发扫描指令到指定类脑盒子"""
        with self._lock_internal:
            box = self._brain_boxes.get(box_id)
            if not box:
                return {"code": -1, "msg": f"类脑盒子 {box_id} 不存在", "data": {}}
            if box.status == BrainBoxStatus.OFFLINE:
                return {"code": -1, "msg": f"类脑盒子 {box_id} 离线", "data": {}}
            base_url = box.base_url

        result = self._client.scan_drones(base_url)
        return {"code": 0, "msg": "success", "data": result}

    def forward_query_drones(self, box_id: str, query: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """转发查询指令到指定类脑盒子"""
        with self._lock_internal:
            box = self._brain_boxes.get(box_id)
            if not box:
                return {"code": -1, "msg": f"类脑盒子 {box_id} 不存在", "data": {}}
            if box.status == BrainBoxStatus.OFFLINE:
                return {"code": -1, "msg": f"类脑盒子 {box_id} 离线", "data": {}}
            base_url = box.base_url

        result = self._client.query_drones(base_url, query)
        return {"code": 0, "msg": "success", "data": result}

    def forward_command(self, box_id: str, device_id: str, command: Dict[str, Any]) -> Dict[str, Any]:
        """转发控制指令到指定类脑盒子"""
        with self._lock_internal:
            box = self._brain_boxes.get(box_id)
            if not box:
                return {"code": -1, "msg": f"类脑盒子 {box_id} 不存在", "data": {}}
            if box.status == BrainBoxStatus.OFFLINE:
                return {"code": -1, "msg": f"类脑盒子 {box_id} 离线", "data": {}}
            base_url = box.base_url

        result = self._client.send_command(base_url, device_id, command)
        return {"code": 0, "msg": "success", "data": result}

    # ==================================================================
    #  导航任务
    # ==================================================================

    def send_navigation_instruction(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        下发导航指令（异步转发）

        创建本地任务记录后，在后台线程中将导航指令转发给 brain_box，
        立即返回任务信息（status=PENDING）。

        brain_box 生成轨迹后会通过 trajectory_report 回调更新任务状态，
        如果同步等待 brain_box 响应会导致死锁：
        edge_server 等待 brain_box → brain_box 生成轨迹后 POST 回 edge_server → 但 edge_server 被阻塞。
        """
        box_id = params.get("box_id", "")
        device_id = params.get("device_id", "")
        instruction_id = params.get("instruction_id", "")
        target_position = params.get("target_position", {})
        algorithm = params.get("algorithm", "simple_linear")
        parameters = params.get("parameters", {})

        with self._lock_internal:
            box = self._brain_boxes.get(box_id)
            if not box:
                return {"code": -1, "msg": f"类脑盒子 {box_id} 不存在", "data": {}}
            if box.status == BrainBoxStatus.OFFLINE:
                return {"code": -1, "msg": f"类脑盒子 {box_id} 离线", "data": {}}
            base_url = box.base_url

            task = NavigationTask(
                task_id=NavigationTask.generate_task_id(),
                instruction_id=instruction_id,
                box_id=box_id,
                device_id=device_id,
                target_position=target_position,
                algorithm=algorithm,
                parameters=parameters,
                status=NavigationStatus.PENDING,
            )
            self._tasks[task.task_id] = task

        def _forward():
            result = self._client.navigation_instruction(
                base_url=base_url,
                instruction_id=instruction_id,
                device_id=device_id,
                target_position=target_position,
                algorithm=algorithm,
                parameters=parameters,
            )
            with self._lock_internal:
                if result.get("success", False):
                    data = result.get("data", {})
                    task.trajectory_id = data.get("trajectory_id")
                    task.status = NavigationStatus.EXECUTING
                    task.result = data
                else:
                    task.status = NavigationStatus.FAILED
                    task.result = result
            logger.info(
                "Navigation instruction forwarded: task=%s box=%s device=%s success=%s",
                task.task_id, box_id, device_id, result.get("success", False),
            )

        thread = threading.Thread(target=_forward, daemon=True)
        thread.start()

        logger.info(
            "Navigation instruction dispatched: task=%s box=%s device=%s",
            task.task_id, box_id, device_id,
        )
        return {"code": 0, "msg": "success", "data": task.to_dict()}

    def execute_trajectory(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """转发轨迹执行指令"""
        box_id = params.get("box_id", "")
        trajectory_id = params.get("trajectory_id", "")

        with self._lock_internal:
            box = self._brain_boxes.get(box_id)
            if not box:
                return {"code": -1, "msg": f"类脑盒子 {box_id} 不存在", "data": {}}
            if box.status == BrainBoxStatus.OFFLINE:
                return {"code": -1, "msg": f"类脑盒子 {box_id} 离线", "data": {}}
            base_url = box.base_url

        result = self._client.execute_trajectory(base_url, trajectory_id)
        return {"code": 0, "msg": "success", "data": result}

    def list_tasks(self, box_id: str = "all") -> Dict[str, Any]:
        """查询导航任务列表"""
        with self._lock_internal:
            tasks = list(self._tasks.values())
            if box_id != "all":
                tasks = [t for t in tasks if t.box_id == box_id]
            return {
                "code": 0,
                "msg": "success",
                "data": {
                    "total": len(tasks),
                    "tasks": [t.to_dict() for t in tasks],
                },
            }

    def get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务详情"""
        with self._lock_internal:
            task = self._tasks.get(task_id)
            if not task:
                return None
            return task.to_dict()

    # ==================================================================
    #  状态管理
    # ==================================================================

    def mark_brain_box_offline(self, box_id: str, reason: str = "unknown") -> None:
        with self._lock_internal:
            box = self._brain_boxes.get(box_id)
            if box:
                box.status = BrainBoxStatus.OFFLINE
                logger.warning("BrainBox marked offline: %s (reason=%s)", box_id, reason)

                for dev in self._devices.values():
                    if dev.box_id == box_id and dev.status != DeviceStatus.OFFLINE:
                        dev.status = DeviceStatus.OFFLINE

                if self._on_box_offline:
                    self._on_box_offline(box)

    def get_all_brain_boxes(self) -> List[BrainBoxNode]:
        with self._lock_internal:
            return list(self._brain_boxes.values())

    def get_brain_box_status(self, box_id: str) -> Dict[str, Any]:
        """查询类脑盒子详细状态（远程调用）"""
        with self._lock_internal:
            box = self._brain_boxes.get(box_id)
            if not box:
                return {"code": -1, "msg": f"类脑盒子 {box_id} 不存在", "data": {}}
            if box.status == BrainBoxStatus.OFFLINE:
                return {"code": -1, "msg": f"类脑盒子 {box_id} 离线", "data": {}}
            base_url = box.base_url

        result = self._client.system_status(base_url)
        return {"code": 0, "msg": "success", "data": result}

    def shutdown(self) -> None:
        self._heartbeat.stop()
        logger.info("EdgeManager shutdown complete")
