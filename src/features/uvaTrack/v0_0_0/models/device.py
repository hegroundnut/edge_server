"""
无人机设备模型 — 由类脑盒子上报，绑定到对应的 brain_box
"""
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from .base import DeviceStatus


@dataclass
class DroneDevice:
    """
    无人机设备（由类脑盒子上报）

    属性:
        device_id: 设备唯一标识
        box_id: 所属类脑盒子 ID
        device_type: 设备类型 (quadcopter, hexarotor 等)
        protocol: 通信协议 (mavlink 等)
        status: 设备状态
        last_heartbeat: 最后心跳时间戳
        position: 位置信息 {latitude, longitude, altitude}
        metadata: 自定义元数据
    """
    device_id: str
    box_id: str
    device_type: str = "quadcopter"
    protocol: str = "mavlink"
    status: DeviceStatus = DeviceStatus.ONLINE
    last_heartbeat: float = field(default_factory=time.time)
    position: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "box_id": self.box_id,
            "device_type": self.device_type,
            "protocol": self.protocol,
            "status": self.status.value,
            "last_heartbeat": self.last_heartbeat,
            "position": dict(self.position),
            "metadata": dict(self.metadata),
        }
