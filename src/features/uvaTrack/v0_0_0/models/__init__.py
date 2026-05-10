"""
数据模型模块
"""
from .base import DeviceStatus, ServerStatus, TaskStatus, ChannelType
from .device import EdgeDevice
from .server import ServerNode
from .task import TaskRecord, StreamChannel, TaskResult, DeviceTelemetry

__all__ = [
    "DeviceStatus",
    "ServerStatus",
    "TaskStatus",
    "ChannelType",
    "EdgeDevice",
    "ServerNode",
    "TaskRecord",
    "StreamChannel",
    "TaskResult",
    "DeviceTelemetry",
]
