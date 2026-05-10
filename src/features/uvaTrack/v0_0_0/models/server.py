"""
计算服务器模型
"""
import time
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from .base import ServerStatus


@dataclass
class ServerNode:
    """
    计算服务器节点
    
    属性:
        server_id: 服务器唯一标识
        ip_address: IP 地址
        capacity: 最大并发任务数
        tags: 服务器标签（如 gpu, path_planning 等）
        status: 服务器状态
        last_heartbeat: 最后心跳时间戳
        current_load: 当前负载（运行中的任务数）
        metadata: 自定义元数据
    """
    server_id: str
    ip_address: str
    capacity: int = 10
    tags: List[str] = field(default_factory=list)
    status: ServerStatus = ServerStatus.ONLINE
    last_heartbeat: float = field(default_factory=time.time)
    current_load: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "server_id": self.server_id,
            "ip_address": self.ip_address,
            "capacity": self.capacity,
            "tags": list(self.tags),
            "status": self.status.value,
            "last_heartbeat": self.last_heartbeat,
            "current_load": self.current_load,
            "available_capacity": self.capacity - self.current_load,
            "metadata": dict(self.metadata),
        }
