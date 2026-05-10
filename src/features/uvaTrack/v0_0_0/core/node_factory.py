"""
节点工厂 - 用于自动识别和创建陌生设备/服务器
"""
import logging
from typing import Dict, Any, Optional, Callable
from models import EdgeDevice, ServerNode

logger = logging.getLogger(__name__)


class NodeFactory:
    """
    节点工厂
    
    根据心跳消息中的元数据自动识别和创建设备或服务器节点。
    支持扩展：新增节点类型只需注册对应的处理器。
    """
    
    def __init__(self):
        """初始化节点工厂"""
        self._device_handlers: Dict[str, Callable] = {}
        self._server_handlers: Dict[str, Callable] = {}
        
        # 注册默认处理器
        self._register_default_handlers()
    
    def _register_default_handlers(self) -> None:
        """注册默认的硬件类型处理器"""
        # 设备处理器
        self._device_handlers["jetson_xavier_nx"] = self._create_jetson_device
        self._device_handlers["jetson_nano"] = self._create_jetson_device
        self._device_handlers["raspberry_pi"] = self._create_raspberry_device
        self._device_handlers["default"] = self._create_default_device
        
        # 服务器处理器
        self._server_handlers["gpu_server"] = self._create_gpu_server
        self._server_handlers["cpu_server"] = self._create_cpu_server
        self._server_handlers["default"] = self._create_default_server
    
    def register_device_handler(
        self,
        hardware_type: str,
        handler: Callable[[str, Dict[str, Any]], EdgeDevice],
    ) -> None:
        """
        注册自定义设备处理器
        
        参数:
            hardware_type: 硬件类型标识
            handler: 处理器函数，签名为 (device_id, metadata) -> EdgeDevice
        """
        self._device_handlers[hardware_type] = handler
        logger.info(f"Device handler registered: {hardware_type}")
    
    def register_server_handler(
        self,
        server_type: str,
        handler: Callable[[str, str, Dict[str, Any]], ServerNode],
    ) -> None:
        """
        注册自定义服务器处理器
        
        参数:
            server_type: 服务器类型标识
            handler: 处理器函数，签名为 (server_id, ip_address, metadata) -> ServerNode
        """
        self._server_handlers[server_type] = handler
        logger.info(f"Server handler registered: {server_type}")
    
    def create_device_from_heartbeat(
        self,
        device_id: str,
        heartbeat_data: Dict[str, Any],
    ) -> Optional[EdgeDevice]:
        """
        从心跳消息创建设备
        
        参数:
            device_id: 设备 ID
            heartbeat_data: 心跳数据（应包含 metadata 字段）
        
        返回:
            创建的 EdgeDevice，如果失败返回 None
        """
        try:
            metadata = heartbeat_data.get("metadata", {})
            hardware_type = metadata.get("hardware_type", "default")
            
            # 获取对应的处理器
            handler = self._device_handlers.get(
                hardware_type,
                self._device_handlers.get("default"),
            )
            
            if handler is None:
                logger.warning(f"No handler found for device type: {hardware_type}")
                return None
            
            device = handler(device_id, metadata)
            logger.info(f"Device created from heartbeat: {device_id} ({hardware_type})")
            return device
        except Exception as e:
            logger.error(f"Failed to create device from heartbeat: {e}")
            return None
    
    def create_server_from_heartbeat(
        self,
        server_id: str,
        heartbeat_data: Dict[str, Any],
    ) -> Optional[ServerNode]:
        """
        从心跳消息创建服务器
        
        参数:
            server_id: 服务器 ID
            heartbeat_data: 心跳数据（应包含 metadata 和 ip_address 字段）
        
        返回:
            创建的 ServerNode，如果失败返回 None
        """
        try:
            metadata = heartbeat_data.get("metadata", {})
            server_type = metadata.get("server_type", "default")
            ip_address = heartbeat_data.get("ip_address", "127.0.0.1")
            
            # 获取对应的处理器
            handler = self._server_handlers.get(
                server_type,
                self._server_handlers.get("default"),
            )
            
            if handler is None:
                logger.warning(f"No handler found for server type: {server_type}")
                return None
            
            server = handler(server_id, ip_address, metadata)
            logger.info(f"Server created from heartbeat: {server_id} ({server_type})")
            return server
        except Exception as e:
            logger.error(f"Failed to create server from heartbeat: {e}")
            return None
    
    # ====================================================================
    #  默认设备处理器
    # ====================================================================
    
    def _create_jetson_device(
        self,
        device_id: str,
        metadata: Dict[str, Any],
    ) -> EdgeDevice:
        """创建 Jetson 系列设备"""
        return EdgeDevice(
            device_id=device_id,
            hardware_type=metadata.get("hardware_type", "jetson_xavier_nx"),
            is_simulated=metadata.get("is_simulated", False),
            supported_streams=set(metadata.get("supported_streams", ["video", "lidar_point_cloud"])),
            group_id=metadata.get("group_id", "jetson"),
            metadata=metadata,
        )
    
    def _create_raspberry_device(
        self,
        device_id: str,
        metadata: Dict[str, Any],
    ) -> EdgeDevice:
        """创建树莓派设备"""
        return EdgeDevice(
            device_id=device_id,
            hardware_type=metadata.get("hardware_type", "raspberry_pi"),
            is_simulated=metadata.get("is_simulated", False),
            supported_streams=set(metadata.get("supported_streams", ["video"])),
            group_id=metadata.get("group_id", "raspberry"),
            metadata=metadata,
        )
    
    def _create_default_device(
        self,
        device_id: str,
        metadata: Dict[str, Any],
    ) -> EdgeDevice:
        """创建默认设备"""
        return EdgeDevice(
            device_id=device_id,
            hardware_type=metadata.get("hardware_type", "unknown"),
            is_simulated=metadata.get("is_simulated", False),
            supported_streams=set(metadata.get("supported_streams", [])),
            group_id=metadata.get("group_id", "default"),
            metadata=metadata,
        )
    
    # ====================================================================
    #  默认服务器处理器
    # ====================================================================
    
    def _create_gpu_server(
        self,
        server_id: str,
        ip_address: str,
        metadata: Dict[str, Any],
    ) -> ServerNode:
        """创建 GPU 服务器"""
        return ServerNode(
            server_id=server_id,
            ip_address=ip_address,
            capacity=metadata.get("capacity", 10),
            tags=metadata.get("tags", ["gpu", "high_compute"]),
            metadata=metadata,
        )
    
    def _create_cpu_server(
        self,
        server_id: str,
        ip_address: str,
        metadata: Dict[str, Any],
    ) -> ServerNode:
        """创建 CPU 服务器"""
        return ServerNode(
            server_id=server_id,
            ip_address=ip_address,
            capacity=metadata.get("capacity", 5),
            tags=metadata.get("tags", ["cpu"]),
            metadata=metadata,
        )
    
    def _create_default_server(
        self,
        server_id: str,
        ip_address: str,
        metadata: Dict[str, Any],
    ) -> ServerNode:
        """创建默认服务器"""
        return ServerNode(
            server_id=server_id,
            ip_address=ip_address,
            capacity=metadata.get("capacity", 5),
            tags=metadata.get("tags", []),
            metadata=metadata,
        )
