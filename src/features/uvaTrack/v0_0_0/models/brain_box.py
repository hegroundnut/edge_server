"""
类脑盒子节点模型
"""
import time
from dataclasses import dataclass, field
from typing import Dict, Any, List
from .base import BrainBoxStatus


@dataclass
class BrainBoxNode:
    """
    类脑盒子节点

    属性:
        box_id: 类脑盒子唯一标识
        ip_address: IP 地址
        port: 服务端口
        status: 运行状态
        last_heartbeat: 最后心跳时间戳
        drone_count: 管辖的无人机总数
        online_drone_count: 在线无人机数
        metadata: 自定义元数据
    """
    box_id: str
    ip_address: str
    port: int = 9000
    status: BrainBoxStatus = BrainBoxStatus.ONLINE
    last_heartbeat: float = field(default_factory=time.time)
    drone_count: int = 0
    online_drone_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def base_url(self) -> str:
        return f"http://{self.ip_address}:{self.port}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "box_id": self.box_id,
            "ip_address": self.ip_address,
            "port": self.port,
            "base_url": self.base_url,
            "status": self.status.value,
            "last_heartbeat": self.last_heartbeat,
            "drone_count": self.drone_count,
            "online_drone_count": self.online_drone_count,
            "metadata": dict(self.metadata),
        }
