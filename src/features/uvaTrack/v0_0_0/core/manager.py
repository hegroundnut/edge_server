"""
边缘服务器核心管理器 — 管理类脑盒子与无人机设备

数据分层:
  - 类脑盒子 (brain_box): 热数据，保留在内存中
  - 无人机设备 (device): 温数据，内存缓存 + DB 持久化
  - 导航任务 (task): 冷数据，活跃任务内存缓存，完成后仅存 DB
  - 心跳日志 (heartbeat_log): 冷数据，直接写 DB
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
from storage import BaseRepository, SQLiteRepository
from .heartbeat import HeartbeatMonitor
from .brain_box_client import BrainBoxClient

logger = logging.getLogger(__name__)


def _create_repository() -> BaseRepository:
    """根据配置创建 Repository 实例"""
    db_type = settings.db_type
    if db_type == "sqlite":
        repo = SQLiteRepository(str(settings.db_path))
    else:
        raise ValueError(f"不支持的数据库类型: {db_type}，目前支持: sqlite")
    repo.initialize()
    return repo


class EdgeManager:
    """
    边缘服务器核心管理器（单例）

    功能:
    - 管理类脑盒子实例 (注册、移除、心跳监控)
    - 管理无人机设备表 (由类脑盒子上报，绑定到对应 brain_box)
    - 转发导航指令到类脑盒子
    - 接收并存储轨迹上报
    - 通过 Repository 持久化冷数据
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
        repository: Optional[BaseRepository] = None,
    ):
        if hasattr(self, "_initialized"):
            return

        self._lock_internal = threading.RLock()

        # 热数据 — 内存
        self._brain_boxes: Dict[str, BrainBoxNode] = {}

        # 温数据 — 内存缓存，写穿到 DB
        self._devices: Dict[str, DroneDevice] = {}

        # 活跃任务缓存（pending/executing/submitted），完成后移到 DB
        self._active_tasks: Dict[str, NavigationTask] = {}

        # 数据库
        self._repo: BaseRepository = repository or _create_repository()

        # 启动时从 DB 恢复活跃任务和设备
        self._restore_from_db()

        self._client = BrainBoxClient(timeout=settings.request_timeout)

        self._heartbeat = HeartbeatMonitor(
            self,
            check_interval_s=heartbeat_interval,
            box_timeout_s=box_timeout,
        )
        self._heartbeat.start()

        self._on_box_offline = on_box_offline

        self._initialized = True
        logger.info("EdgeManager initialized (db=%s)", settings.db_type)

    def _restore_from_db(self) -> None:
        """从数据库恢复活跃任务和设备缓存"""
        for status in ("pending", "executing", "submitted"):
            for task_dict in self._repo.list_tasks(status=status, limit=10000):
                task = _dict_to_task(task_dict)
                self._active_tasks[task.task_id] = task

        for dev_dict in self._repo.list_devices():
            dev = _dict_to_device(dev_dict)
            self._devices[dev.device_id] = dev

        logger.info(
            "Restored from DB: %d active tasks, %d devices",
            len(self._active_tasks),
            len(self._devices),
        )

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

            removed_ids = [
                did for did, d in self._devices.items() if d.box_id == box_id
            ]
            for did in removed_ids:
                self._devices.pop(did)

        # DB 清理（锁外执行，避免持锁做 IO）
        self._repo.delete_devices_by_box(box_id)

        logger.info(
            "BrainBox removed: %s (cleaned %d devices)",
            box_id, len(removed_ids),
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
        心跳数据持久化到数据库。
        """
        box_id = params.get("box_id", "")

        # 持久化心跳日志（不持锁）
        log_data = dict(params)
        if "timestamp" not in log_data:
            log_data["timestamp"] = time.time()
        self._repo.save_heartbeat_log(log_data)

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
        同步写入内存缓存和数据库。
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
        """插入或更新设备记录（内存 + DB）"""
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

        # 写穿到 DB
        self._repo.save_device(dev.to_dict())

    # ==================================================================
    #  轨迹上报（brain_box → edge_server）
    # ==================================================================

    def receive_trajectory_report(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """接收导航轨迹上报"""
        box_id = params.get("box_id", "")
        trajectory = params.get("trajectory", {})

        trajectory_id = trajectory.get("trajectory_id", "")
        device_id = trajectory.get("device_id", "")

        with self._lock_internal:
            matched = False

            # 先按 trajectory_id 匹配
            for task in self._active_tasks.values():
                if task.trajectory_id == trajectory_id and task.status == NavigationStatus.EXECUTING:
                    task.result = trajectory
                    self._persist_task(task)
                    matched = True
                    break

            # 备选：按 box_id + device_id 匹配 pending/executing 任务
            if not matched:
                for task in self._active_tasks.values():
                    if (
                        task.box_id == box_id
                        and task.device_id == device_id
                        and task.status in (NavigationStatus.PENDING, NavigationStatus.EXECUTING)
                    ):
                        task.trajectory_id = trajectory_id
                        task.status = NavigationStatus.EXECUTING
                        task.result = trajectory
                        self._persist_task(task)
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
        """获取无人机设备列表（从 DB 读取）"""
        devices = self._repo.list_devices(box_id)
        return {
            "code": 0,
            "msg": "success",
            "data": {
                "total": len(devices),
                "devices": devices,
            },
        }

    def get_device_info(self, device_id: str) -> Optional[Dict[str, Any]]:
        """获取设备详情"""
        return self._repo.get_device(device_id)

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
            self._active_tasks[task.task_id] = task

        # 持久化新任务
        self._persist_task(task)

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
            self._persist_task(task)
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
        """转发轨迹执行指令，并将任务标记为 SUBMITTED"""
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

        # 更新关联任务状态为 SUBMITTED
        with self._lock_internal:
            for task in self._active_tasks.values():
                if task.trajectory_id == trajectory_id:
                    task.status = NavigationStatus.SUBMITTED
                    task.submitted_at = time.time()
                    self._persist_task(task)
                    logger.info(
                        "Task %s marked as submitted (trajectory=%s)",
                        task.task_id, trajectory_id,
                    )
                    break

        return {"code": 0, "msg": "success", "data": result}

    def list_tasks(
        self,
        box_id: str = "all",
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """查询导航任务列表（从 DB 读取）"""
        tasks = self._repo.list_tasks(
            box_id=box_id, status=status, limit=limit, offset=offset,
        )
        total = self._repo.count_tasks(box_id=box_id, status=status)
        return {
            "code": 0,
            "msg": "success",
            "data": {
                "total": total,
                "tasks": tasks,
            },
        }

    def get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务详情（优先内存，其次 DB）"""
        with self._lock_internal:
            task = self._active_tasks.get(task_id)
            if task:
                return task.to_dict()
        return self._repo.get_task(task_id)

    # ==================================================================
    #  任务持久化辅助
    # ==================================================================

    def _persist_task(self, task: NavigationTask) -> None:
        """将任务写入 DB，完成/失败的任务从活跃缓存中移除"""
        self._repo.save_task(task.to_dict())
        if task.status in (NavigationStatus.COMPLETED, NavigationStatus.FAILED):
            self._active_tasks.pop(task.task_id, None)

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

        # DB 批量更新设备状态
        self._repo.update_device_status_by_box(box_id, "offline")

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
        self._repo.close()
        logger.info("EdgeManager shutdown complete")


# ======================================================================
#  字典 → 模型 转换
# ======================================================================

def _dict_to_task(d: Dict[str, Any]) -> NavigationTask:
    return NavigationTask(
        task_id=d["task_id"],
        instruction_id=d.get("instruction_id", ""),
        box_id=d.get("box_id", ""),
        device_id=d.get("device_id", ""),
        target_position=d.get("target_position", {}),
        algorithm=d.get("algorithm", "simple_linear"),
        parameters=d.get("parameters", {}),
        status=NavigationStatus(d.get("status", "pending")),
        trajectory_id=d.get("trajectory_id"),
        created_at=d.get("created_at", 0),
        submitted_at=d.get("submitted_at"),
        completed_at=d.get("completed_at"),
        result=d.get("result", {}),
    )


def _dict_to_device(d: Dict[str, Any]) -> DroneDevice:
    return DroneDevice(
        device_id=d["device_id"],
        box_id=d.get("box_id", ""),
        device_type=d.get("device_type", "quadcopter"),
        protocol=d.get("protocol", "mavlink"),
        status=DeviceStatus(d.get("status", "online")),
        last_heartbeat=d.get("last_heartbeat", 0),
        position=d.get("position", {}),
        metadata=d.get("metadata", {}),
    )
