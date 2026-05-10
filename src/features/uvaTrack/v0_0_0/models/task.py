"""
任务、流通道、结果和遥测模型
"""
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from .base import TaskStatus, ChannelType


@dataclass
class TaskRecord:
    """
    任务记录
    
    属性:
        task_id: 任务唯一标识
        device_id: 执行任务的设备 ID
        server_id: 处理任务的服务器 ID
        algorithm: 算法名称
        frequency_hz: 执行频率（Hz）
        enable_video_stream: 是否启用视频流
        stream_port: 视频流端口
        custom_payloads: 自定义任务参数
        status: 任务状态
        created_at: 创建时间戳
        stopped_at: 停止时间戳
        stop_reason: 停止原因
    """
    task_id: str
    device_id: str
    server_id: str
    algorithm: str
    frequency_hz: int
    enable_video_stream: bool = False
    stream_port: Optional[int] = None
    custom_payloads: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.RUNNING
    created_at: float = field(default_factory=time.time)
    stopped_at: Optional[float] = None
    stop_reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "device_id": self.device_id,
            "server_id": self.server_id,
            "algorithm": self.algorithm,
            "frequency_hz": self.frequency_hz,
            "enable_video_stream": self.enable_video_stream,
            "stream_port": self.stream_port,
            "custom_payloads": dict(self.custom_payloads),
            "status": self.status.value,
            "created_at": self.created_at,
            "stopped_at": self.stopped_at,
            "stop_reason": self.stop_reason,
        }
    
    @staticmethod
    def generate_task_id() -> str:
        """生成任务 ID"""
        return f"task_{uuid.uuid4().hex[:12]}"


@dataclass
class StreamChannel:
    """
    流通道
    
    属性:
        channel_id: 通道唯一标识
        device_id: 关联的设备 ID
        channel_type: 通道类型（信令或媒体）
        protocol: 传输协议（websocket, webrtc, http, udp）
        port: 通道端口
        stream_type: 数据流类型（video, lidar_point_cloud 等）
        active: 是否活跃
        metadata: 自定义元数据
    """
    channel_id: str
    device_id: str
    channel_type: ChannelType
    protocol: str
    port: int
    stream_type: str
    active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "channel_id": self.channel_id,
            "device_id": self.device_id,
            "channel_type": self.channel_type.value,
            "protocol": self.protocol,
            "port": self.port,
            "stream_type": self.stream_type,
            "active": self.active,
            "metadata": dict(self.metadata),
        }
    
    @staticmethod
    def generate_channel_id() -> str:
        """生成通道 ID"""
        return f"ch_{uuid.uuid4().hex[:10]}"


@dataclass
class TaskResult:
    """
    任务计算结果（通用）
    
    服务器完成计算后提交，result_type 标识结果类型，
    payload 为具体数据（格式由调用方自定义）。
    
    属性:
        result_id: 结果唯一标识
        task_id: 关联的任务 ID
        device_id: 执行设备 ID
        server_id: 处理服务器 ID
        result_type: 结果类型（trajectory, detection, analysis 等）
        payload: 结果数据
        created_at: 创建时间戳
        metadata: 自定义元数据
    """
    result_id: str
    task_id: str
    device_id: str
    server_id: str
    result_type: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "result_id": self.result_id,
            "task_id": self.task_id,
            "device_id": self.device_id,
            "server_id": self.server_id,
            "result_type": self.result_type,
            "payload": dict(self.payload),
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }
    
    @staticmethod
    def generate_result_id() -> str:
        """生成结果 ID"""
        return f"res_{uuid.uuid4().hex[:12]}"


@dataclass
class DeviceTelemetry:
    """
    设备遥测数据（通用）
    
    设备/服务器向边缘服务上报的遥测数据，
    telemetry_type 标识遥测类型，data 为具体数据。
    
    属性:
        device_id: 设备 ID
        telemetry_type: 遥测类型（position, drone_status, sensor 等）
        data: 遥测数据
        timestamp: 时间戳
        metadata: 自定义元数据
    """
    device_id: str
    telemetry_type: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "device_id": self.device_id,
            "telemetry_type": self.telemetry_type,
            "data": dict(self.data),
            "timestamp": self.timestamp,
            "metadata": dict(self.metadata),
        }
