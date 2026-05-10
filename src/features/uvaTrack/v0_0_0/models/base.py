"""
基础数据模型和枚举
"""
from enum import Enum


class DeviceStatus(Enum):
    """设备状态"""
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    ERROR = "error"


class ServerStatus(Enum):
    """服务器状态"""
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    ERROR = "error"


class TaskStatus(Enum):
    """任务状态"""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class ChannelType(Enum):
    """流通道类型"""
    SIGNALING = "signaling"  # 信令通道（低频小包）
    MEDIA = "media"          # 媒体通道（高带宽数据）
