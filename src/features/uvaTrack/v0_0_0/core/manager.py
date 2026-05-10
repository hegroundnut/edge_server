"""
云边协同管控核心调度器 - 单例
"""
import time
import threading
import logging
from typing import Dict, List, Optional, Any, Callable
from models import (
    EdgeDevice,
    ServerNode,
    TaskRecord,
    TaskResult,
    DeviceTelemetry,
    DeviceStatus,
    ServerStatus,
    TaskStatus,
)
from storage import LocalStorage
from config.settings import settings
from .heartbeat import HeartbeatMonitor
from .registry import StreamRegistry
from .node_factory import NodeFactory

logger = logging.getLogger(__name__)


class CloudEdgeManager:
    """
    云边协同管控核心调度器（单例）
    
    功能:
    - 管理服务器节点和边缘设备
    - 调度任务执行
    - 监控心跳和设备状态
    - 管理数据流通道
    - 持久化存储任务和结果
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
        heartbeat_interval: float = 5.0,
        device_timeout: float = 15.0,
        server_timeout: float = 30.0,
        on_task_stopped: Optional[Callable[[TaskRecord], None]] = None,
    ):
        """
        初始化管理器
        
        参数:
            heartbeat_interval: 心跳检查间隔（秒）
            device_timeout: 设备心跳超时（秒）
            server_timeout: 服务器心跳超时（秒）
            on_task_stopped: 任务停止回调函数
        """
        if hasattr(self, "_initialized"):
            return
        
        self._lock_internal = threading.RLock()
        
        # 节点存储
        self._servers: Dict[str, ServerNode] = {}
        self._devices: Dict[str, EdgeDevice] = {}
        self._removed_nodes: set = set()  # 黑名单：已移除的节点 ID
        
        # 任务和结果存储
        self._tasks: Dict[str, TaskRecord] = {}
        self._task_results: Dict[str, List[TaskResult]] = {}
        self._device_telemetry: Dict[str, DeviceTelemetry] = {}
        
        # 流通道管理
        self._stream_registry = StreamRegistry()
        
        # 存储管理
        self._storage = LocalStorage()
        
        # 节点工厂（用于自动识别）
        self._node_factory = NodeFactory()
        
        # 心跳监控
        self._heartbeat = HeartbeatMonitor(
            self,
            check_interval_s=heartbeat_interval,
            device_timeout_s=device_timeout,
            server_timeout_s=server_timeout,
        )
        self._heartbeat.start()
        
        # 回调
        self._on_task_stopped = on_task_stopped
        
        self._initialized = True
        logger.info("CloudEdgeManager initialized")
    
    # ==================================================================
    #  服务器管理
    # ==================================================================
    
    def add_server(
        self,
        server_id: str,
        ip_address: str,
        capacity: int = 10,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        注册计算服务器节点到云端调度池
        
        参数:
            server_id: 服务器 ID
            ip_address: IP 地址
            capacity: 最大并发任务数
            tags: 服务器标签
            metadata: 自定义元数据
        
        返回:
            操作结果字典
        """
        with self._lock_internal:
            if server_id in self._servers:
                return {
                    "code": -1,
                    "msg": f"服务器 {server_id} 已存在",
                    "data": {},
                }
            
            # 从黑名单中移除（如果存在）
            self._removed_nodes.discard(server_id)
            
            server = ServerNode(
                server_id=server_id,
                ip_address=ip_address,
                capacity=capacity,
                tags=tags or [],
                metadata=metadata or {},
            )
            self._servers[server_id] = server
            logger.info(f"Server added: {server_id} ({ip_address})")
            
            return {
                "code": 0,
                "msg": "success",
                "data": server.to_dict(),
            }
    
    def remove_server(
        self,
        server_id: str,
        force_stop: bool = False,
    ) -> Dict[str, Any]:
        """
        从调度池中安全移除指定服务器
        
        参数:
            server_id: 服务器 ID
            force_stop: 是否强制停止所有任务
        
        返回:
            操作结果字典
        """
        with self._lock_internal:
            if server_id not in self._servers:
                return {
                    "code": -1,
                    "msg": f"服务器 {server_id} 不存在",
                    "data": {},
                }
            
            # 停止所有运行中的任务
            if force_stop:
                tasks_on_server = self._get_tasks_on_server(server_id)
                for task in tasks_on_server:
                    self._stop_task_internal(task.task_id, reason="server_removed")
            
            server = self._servers.pop(server_id)
            self._removed_nodes.add(server_id)  # 加入黑名单
            logger.info(f"Server removed: {server_id}")
            
            return {
                "code": 0,
                "msg": "success",
                "data": server.to_dict(),
            }
    
    def list_servers(self, filter_by_status: str = "all") -> Dict[str, Any]:
        """
        获取可用的计算服务器列表及当前负载状态
        
        参数:
            filter_by_status: 按状态过滤（all, online, offline, busy）
        
        返回:
            操作结果字典
        """
        with self._lock_internal:
            servers = list(self._servers.values())
            
            if filter_by_status != "all":
                servers = [
                    s for s in servers
                    if s.status.value == filter_by_status
                ]
            
            return {
                "code": 0,
                "msg": "success",
                "data": {
                    "total": len(servers),
                    "servers": [s.to_dict() for s in servers],
                },
            }
    
    # ==================================================================
    #  设备管理
    # ==================================================================
    
    def add_device(
        self,
        device_id: str,
        hardware_type: str,
        is_simulated: bool = False,
        supported_streams: Optional[List[str]] = None,
        group_id: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        注册边缘设备到管控系统
        
        参数:
            device_id: 设备 ID
            hardware_type: 硬件类型
            is_simulated: 是否为模拟设备
            supported_streams: 支持的数据流类型
            group_id: 设备分组
            metadata: 自定义元数据
        
        返回:
            操作结果字典
        """
        with self._lock_internal:
            if device_id in self._devices:
                return {
                    "code": -1,
                    "msg": f"设备 {device_id} 已存在",
                    "data": {},
                }
            
            # 从黑名单中移除（如果存在）
            self._removed_nodes.discard(device_id)
            
            device = EdgeDevice(
                device_id=device_id,
                hardware_type=hardware_type,
                is_simulated=is_simulated,
                supported_streams=set(supported_streams or []),
                group_id=group_id,
                metadata=metadata or {},
            )
            self._devices[device_id] = device
            logger.info(f"Device added: {device_id} ({hardware_type})")
            
            return {
                "code": 0,
                "msg": "success",
                "data": device.to_dict(),
            }
    
    def remove_device(self, device_id: str) -> Dict[str, Any]:
        """
        从系统中注销边缘设备
        
        参数:
            device_id: 设备 ID
        
        返回:
            操作结果字典
        """
        with self._lock_internal:
            if device_id not in self._devices:
                return {
                    "code": -1,
                    "msg": f"设备 {device_id} 不存在",
                    "data": {},
                }
            
            device = self._devices.pop(device_id)
            self._removed_nodes.add(device_id)  # 加入黑名单
            
            # 关闭设备的所有数据流
            self._stream_registry.close_device_channels(device_id)
            
            # 停止设备的活跃任务
            if device.active_task_id:
                self._stop_task_internal(
                    device.active_task_id,
                    reason="device_removed",
                )
            
            logger.info(f"Device removed: {device_id}")
            
            return {
                "code": 0,
                "msg": "success",
                "data": device.to_dict(),
            }
    
    def list_devices(self, group_id: str = "all") -> Dict[str, Any]:
        """
        获取已注册的边缘设备列表及在线状态
        
        参数:
            group_id: 按分组过滤（all 表示不过滤）
        
        返回:
            操作结果字典
        """
        with self._lock_internal:
            devices = list(self._devices.values())
            
            if group_id != "all":
                devices = [d for d in devices if d.group_id == group_id]
            
            return {
                "code": 0,
                "msg": "success",
                "data": {
                    "total": len(devices),
                    "devices": [d.to_dict() for d in devices],
                },
            }
    
    # ==================================================================
    #  核心调度
    # ==================================================================
    
    def assign_and_start_task(
        self,
        device_id: str,
        server_id: str,
        task_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        核心调度：指定边缘设备连接特定服务器执行计算任务
        
        参数:
            device_id: 设备 ID
            server_id: 服务器 ID
            task_config: 任务配置（包含 algorithm, frequency_hz 等）
        
        返回:
            操作结果字典
        """
        with self._lock_internal:
            # 验证设备和服务器存在
            if device_id not in self._devices:
                return {
                    "code": -1,
                    "msg": f"设备 {device_id} 不存在",
                    "data": {},
                }
            
            if server_id not in self._servers:
                return {
                    "code": -1,
                    "msg": f"服务器 {server_id} 不存在",
                    "data": {},
                }
            
            device = self._devices[device_id]
            server = self._servers[server_id]
            
            # 检查服务器容量
            if server.current_load >= server.capacity:
                return {
                    "code": -1,
                    "msg": f"服务器 {server_id} 容量已满",
                    "data": {},
                }
            
            # 如果设备已有活跃任务，先停止旧任务（任务抢占）
            if device.active_task_id:
                self._stop_task_internal(
                    device.active_task_id,
                    reason="task_preempted",
                )
            
            # 创建新任务
            task_config = task_config or {}
            task = TaskRecord(
                task_id=TaskRecord.generate_task_id(),
                device_id=device_id,
                server_id=server_id,
                algorithm=task_config.get("algorithm", "unknown"),
                frequency_hz=task_config.get("frequency_hz", 10),
                enable_video_stream=task_config.get("enable_video_stream", False),
                stream_port=task_config.get("stream_port"),
                custom_payloads=task_config.get("custom_payloads", {}),
            )
            
            # 更新状态
            self._tasks[task.task_id] = task
            device.active_task_id = task.task_id
            device.assigned_server_id = server_id
            device.status = DeviceStatus.BUSY
            server.current_load += 1
            
            # 持久化存储
            self._storage.save_task(task.task_id, task.to_dict())
            
            logger.info(
                f"Task assigned: {task.task_id} (device={device_id}, server={server_id})"
            )
            
            return {
                "code": 0,
                "msg": "success",
                "data": task.to_dict(),
            }
    
    def stop_task(
        self,
        device_id: str,
        reason: str = "user_manual_stop",
    ) -> Dict[str, Any]:
        """
        中断指定设备与服务器之间的任务和数据流
        
        参数:
            device_id: 设备 ID
            reason: 停止原因
        
        返回:
            操作结果字典
        """
        with self._lock_internal:
            if device_id not in self._devices:
                return {
                    "code": -1,
                    "msg": f"设备 {device_id} 不存在",
                    "data": {},
                }
            
            device = self._devices[device_id]
            if not device.active_task_id:
                return {
                    "code": -1,
                    "msg": f"设备 {device_id} 没有活跃任务",
                    "data": {},
                }
            
            task_id = device.active_task_id
            result = self._stop_task_internal(task_id, reason=reason)
            
            return {
                "code": 0,
                "msg": "success",
                "data": result,
            }
    
    def _stop_task_internal(
        self,
        task_id: str,
        reason: str = "unknown",
    ) -> Dict[str, Any]:
        """内部停止任务方法"""
        task = self._tasks.get(task_id)
        if not task or task.status != TaskStatus.RUNNING:
            return {}
        
        # 更新任务状态
        task.status = TaskStatus.STOPPED
        task.stopped_at = time.time()
        task.stop_reason = reason
        
        # 更新设备状态
        device = self._devices.get(task.device_id)
        if device:
            device.active_task_id = None
            device.assigned_server_id = None
            device.status = DeviceStatus.ONLINE
        
        # 更新服务器负载
        server = self._servers.get(task.server_id)
        if server:
            server.current_load = max(0, server.current_load - 1)
        
        # 关闭数据流
        self._stream_registry.close_device_channels(task.device_id)
        
        # 持久化存储
        self._storage.save_task(task_id, task.to_dict())
        
        # 触发回调
        if self._on_task_stopped:
            self._on_task_stopped(task)
        
        logger.info(f"Task stopped: {task_id} (reason={reason})")
        
        return task.to_dict()
    
    # ==================================================================
    #  心跳处理（支持自动识别和添加）
    # ==================================================================
    
    def refresh_device_heartbeat(
        self,
        device_id: str,
        location: Optional[Dict[str, Any]] = None,
        heartbeat_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        刷新设备心跳
        
        如果设备不存在且未被移除，则尝试自动注册。
        
        参数:
            device_id: 设备 ID
            location: 位置信息
            heartbeat_data: 完整心跳数据（用于自动注册）
        
        返回:
            是否成功
        """
        with self._lock_internal:
            # 检查黑名单
            if device_id in self._removed_nodes:
                logger.debug(f"Device {device_id} in blacklist, ignoring heartbeat")
                return False
            
            # 设备已存在
            if device_id in self._devices:
                device = self._devices[device_id]
                device.last_active_time = time.time()
                if location:
                    device.location = dict(location)
                if device.status == DeviceStatus.OFFLINE:
                    device.status = DeviceStatus.ONLINE
                logger.debug(f"Device heartbeat refreshed: {device_id}")
                return True
            
            # 设备不存在，尝试自动注册
            if not settings.auto_register_enabled:
                logger.debug(f"Auto-register disabled, device {device_id} not found")
                return False
            
            if heartbeat_data is None:
                logger.debug(f"No heartbeat data for auto-register, device {device_id}")
                return False
            
            device = self._node_factory.create_device_from_heartbeat(
                device_id,
                heartbeat_data,
            )
            
            if device is None:
                logger.warning(f"Failed to auto-register device: {device_id}")
                return False
            
            # 设置位置信息
            if location:
                device.location = dict(location)
            
            # 添加到设备列表
            self._devices[device_id] = device
            logger.info(f"Device auto-registered from heartbeat: {device_id}")
            return True
    
    def refresh_server_heartbeat(self, server_id: str) -> bool:
        """
        刷新服务器心跳
        
        如果服务器不存在且未被移除，则尝试自动注册。
        
        参数:
            server_id: 服务器 ID
        
        返回:
            是否成功
        """
        with self._lock_internal:
            # 检查黑名单
            if server_id in self._removed_nodes:
                logger.debug(f"Server {server_id} in blacklist, ignoring heartbeat")
                return False
            
            # 服务器已存在
            if server_id in self._servers:
                server = self._servers[server_id]
                server.last_heartbeat = time.time()
                if server.status == ServerStatus.OFFLINE:
                    server.status = ServerStatus.ONLINE
                logger.debug(f"Server heartbeat refreshed: {server_id}")
                return True
            
            logger.debug(f"Server {server_id} not found and auto-register not applicable")
            return False
    
    # ==================================================================
    #  状态管理
    # ==================================================================
    
    def mark_device_offline(
        self,
        device_id: str,
        reason: str = "unknown",
    ) -> None:
        """标记设备离线"""
        with self._lock_internal:
            device = self._devices.get(device_id)
            if device:
                device.status = DeviceStatus.OFFLINE
                logger.warning(f"Device marked offline: {device_id} (reason={reason})")
    
    def mark_server_offline(
        self,
        server_id: str,
        reason: str = "unknown",
    ) -> None:
        """标记服务器离线"""
        with self._lock_internal:
            server = self._servers.get(server_id)
            if server:
                server.status = ServerStatus.OFFLINE
                logger.warning(f"Server marked offline: {server_id} (reason={reason})")
    
    # ==================================================================
    #  查询接口
    # ==================================================================
    
    def get_device_info(self, device_id: str) -> Optional[Dict[str, Any]]:
        """获取设备详细信息"""
        with self._lock_internal:
            device = self._devices.get(device_id)
            if not device:
                return None
            info = device.to_dict()
            info["stream_channels"] = self._stream_registry.get_channels_by_device(
                device_id
            )
            if device.active_task_id:
                task = self._tasks.get(device.active_task_id)
                info["active_task"] = task.to_dict() if task else None
            telemetry = self._device_telemetry.get(device_id)
            info["latest_telemetry"] = telemetry.to_dict() if telemetry else None
            return info
    
    def get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务详情"""
        with self._lock_internal:
            task = self._tasks.get(task_id)
            if not task:
                return None
            info = task.to_dict()
            results = self._task_results.get(task_id, [])
            info["results"] = [r.to_dict() for r in results]
            return info
    
    def get_all_devices(self) -> List[EdgeDevice]:
        """获取所有设备（供心跳监控器调用）"""
        with self._lock_internal:
            return list(self._devices.values())
    
    def get_all_servers(self) -> List[ServerNode]:
        """获取所有服务器（供心跳监控器调用）"""
        with self._lock_internal:
            return list(self._servers.values())
    
    def _get_tasks_on_server(self, server_id: str) -> List[TaskRecord]:
        """获取服务器上的所有任务"""
        return [
            t
            for t in self._tasks.values()
            if t.server_id == server_id and t.status == TaskStatus.RUNNING
        ]
    
    # ==================================================================
    #  通用数据交互（设备无关）
    # ==================================================================
    
    def submit_task_result(
        self,
        task_id: str,
        result_type: str,
        payload: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """提交任务计算结果"""
        with self._lock_internal:
            task = self._tasks.get(task_id)
            if not task:
                return {"code": -1, "msg": f"任务 {task_id} 不存在", "data": {}}
            
            result = TaskResult(
                result_id=TaskResult.generate_result_id(),
                task_id=task_id,
                device_id=task.device_id,
                server_id=task.server_id,
                result_type=result_type,
                payload=dict(payload) if payload else {},
                metadata=dict(metadata) if metadata else {},
            )
            self._task_results.setdefault(task_id, []).append(result)
            
            # 持久化存储
            self._storage.save_result(result.result_id, result.to_dict())
            
            logger.info(
                "Task result submitted: %s type=%s task=%s",
                result.result_id,
                result_type,
                task_id,
            )
            
            return {
                "code": 0,
                "msg": "success",
                "data": result.to_dict(),
            }
    
    def update_device_telemetry(
        self,
        device_id: str,
        telemetry_type: str,
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """更新设备遥测数据"""
        with self._lock_internal:
            device = self._devices.get(device_id)
            if not device:
                return {"code": -1, "msg": f"设备 {device_id} 不存在", "data": {}}
            
            telemetry = DeviceTelemetry(
                device_id=device_id,
                telemetry_type=telemetry_type,
                data=dict(data) if data else {},
                metadata=dict(metadata) if metadata else {},
            )
            self._device_telemetry[device_id] = telemetry
            
            # 从遥测数据中提取位置信息
            position = (data or {}).get("position")
            if position and isinstance(position, dict):
                device.location = dict(position)
            
            device.last_active_time = time.time()
            
            # 持久化存储
            self._storage.save_telemetry(device_id, telemetry.to_dict())
            
            logger.info(
                "Telemetry updated: device=%s type=%s",
                device_id,
                telemetry_type,
            )
            
            return {
                "code": 0,
                "msg": "success",
                "data": telemetry.to_dict(),
            }
    
    def shutdown(self) -> None:
        """关闭管理器"""
        self._heartbeat.stop()
        with self._lock_internal:
            running_tasks = [
                t for t in self._tasks.values() if t.status == TaskStatus.RUNNING
            ]
            for task in running_tasks:
                self._stop_task_internal(task.task_id, reason="system_shutdown")
        logger.info("CloudEdgeManager shutdown complete")
