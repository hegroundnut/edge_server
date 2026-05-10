"""
基础数据模型和枚举
"""
from enum import Enum


class BrainBoxStatus(Enum):
    """类脑盒子状态"""
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"


class DeviceStatus(Enum):
    """无人机设备状态"""
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    ERROR = "error"


class NavigationStatus(Enum):
    """导航任务状态"""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
