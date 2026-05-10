"""
边缘设备模型
"""
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Set
from .base import DeviceStatus


@dataclass
class EdgeDevice:
    """
    边缘设备
    
    属性:
        device_id: 设备唯一标识
        hardware_type: 硬件类型（如 jetson_xavier_nx, raspberry_pi 等）
        is_simulated: 是否为模拟设备（模拟设备跳过心跳检测）
        supported_streams: 支持的数据流类型列表
        group_id: 设备分组
        status: 设备状态
        last_active_time: 最后活跃时间戳
        assigned_server_id: 分配的服务器 ID
        active_task_id: 当前活跃任务 ID
        location: 设备位置信息
        metadata: 自定义元数据
    """
    device_id: str
    hardware_type: str
    is_simulated: bool = False
    supported_streams: Set[str] = field(default_factory=set)
    group_id: str = "default"
    status: DeviceStatus = DeviceStatus.ONLINE
    last_active_time: float = field(default_factory=time.time)
    assigned_server_id: Optional[str] = None
    active_task_id: Optional[str] = None
    location: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "device_id": self.device_id,
            "hardware_type": self.hardware_type,
            "is_simulated": self.is_simulated,
            "supported_streams": list(self.supported_streams),
            "group_id": self.group_id,
            "status": self.status.value,
            "last_active_time": self.last_active_time,
            "assigned_server_id": self.assigned_server_id,
            "active_task_id": self.active_task_id,
            "location": dict(self.location),
            "metadata": dict(self.metadata),
        }
