"""
流通道注册表 - 数据流隔离管理
"""
import threading
import logging
from typing import Dict, List, Optional, Any
from models import StreamChannel, ChannelType

logger = logging.getLogger(__name__)


class StreamRegistry:
    """
    流通道注册表，管理所有设备的数据通道。
    
    设计原则:
    - 信令通道 (SIGNALING): 走 HTTP/WebSocket，承载路径下发、状态上报等低频控制消息
    - 媒体通道 (MEDIA): 走 WebRTC/UDP，承载视频流、点云数据等高带宽数据
    - 端口独占: 每个端口只能分配给一个通道，避免冲突
    """
    
    def __init__(self):
        """初始化流通道注册表"""
        self._channels: Dict[str, StreamChannel] = {}
        self._lock = threading.Lock()
        self._port_allocations: Dict[int, str] = {}  # port -> channel_id
    
    def register_channel(
        self,
        device_id: str,
        channel_type: ChannelType,
        protocol: str,
        port: int,
        stream_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[StreamChannel]:
        """
        注册流通道
        
        参数:
            device_id: 设备 ID
            channel_type: 通道类型（信令或媒体）
            protocol: 传输协议
            port: 端口号
            stream_type: 数据流类型
            metadata: 自定义元数据
        
        返回:
            创建的 StreamChannel，如果端口已占用返回 None
        """
        with self._lock:
            if port in self._port_allocations:
                logger.warning(f"Port {port} already allocated")
                return None
            
            channel = StreamChannel(
                channel_id=StreamChannel.generate_channel_id(),
                device_id=device_id,
                channel_type=channel_type,
                protocol=protocol,
                port=port,
                stream_type=stream_type,
                metadata=metadata or {},
            )
            self._channels[channel.channel_id] = channel
            self._port_allocations[port] = channel.channel_id
            logger.info(f"Channel registered: {channel.channel_id} (device={device_id}, port={port})")
            return channel
    
    def unregister_channel(self, channel_id: str) -> Optional[StreamChannel]:
        """
        注销流通道
        
        参数:
            channel_id: 通道 ID
        
        返回:
            被注销的 StreamChannel，如果不存在返回 None
        """
        with self._lock:
            channel = self._channels.pop(channel_id, None)
            if channel:
                self._port_allocations.pop(channel.port, None)
                logger.info(f"Channel unregistered: {channel_id}")
            return channel
    
    def get_channels_by_device(self, device_id: str) -> List[Dict[str, Any]]:
        """
        获取设备的所有通道
        
        参数:
            device_id: 设备 ID
        
        返回:
            通道信息列表
        """
        with self._lock:
            return [
                ch.to_dict()
                for ch in self._channels.values()
                if ch.device_id == device_id
            ]
    
    def close_device_channels(self, device_id: str) -> int:
        """
        关闭设备的所有通道
        
        参数:
            device_id: 设备 ID
        
        返回:
            关闭的通道数
        """
        with self._lock:
            to_remove = [
                cid
                for cid, ch in self._channels.items()
                if ch.device_id == device_id
            ]
            for cid in to_remove:
                ch = self._channels.pop(cid)
                self._port_allocations.pop(ch.port, None)
            logger.info(f"Closed {len(to_remove)} channels for device {device_id}")
            return len(to_remove)
    
    def is_port_available(self, port: int) -> bool:
        """
        检查端口是否可用
        
        参数:
            port: 端口号
        
        返回:
            端口是否可用
        """
        with self._lock:
            return port not in self._port_allocations
    
    def list_all(self) -> List[Dict[str, Any]]:
        """
        列出所有通道
        
        返回:
            所有通道信息列表
        """
        with self._lock:
            return [ch.to_dict() for ch in self._channels.values()]
