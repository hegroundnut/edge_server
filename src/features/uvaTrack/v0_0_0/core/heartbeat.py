"""
心跳监控守护线程
定期检查所有已注册的设备和服务器的活跃状态，
若超时未收到心跳则自动标记为离线并释放相关资源。
"""
import time
import threading
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .manager import CloudEdgeManager

logger = logging.getLogger(__name__)


class HeartbeatMonitor:
    """
    心跳监控器
    
    参数:
        manager: CloudEdgeManager 实例
        check_interval_s: 检查间隔（秒），默认 5s
        device_timeout_s: 设备心跳超时（秒），默认 15s
        server_timeout_s: 服务器心跳超时（秒），默认 30s
    """
    
    def __init__(
        self,
        manager: "CloudEdgeManager",
        check_interval_s: float = 5.0,
        device_timeout_s: float = 15.0,
        server_timeout_s: float = 30.0,
    ):
        self._manager = manager
        self._check_interval = check_interval_s
        self._device_timeout = device_timeout_s
        self._server_timeout = server_timeout_s
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
    
    def start(self) -> None:
        """启动心跳监控"""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop, name="heartbeat-monitor", daemon=True
        )
        self._thread.start()
        logger.info(
            "HeartbeatMonitor started (interval=%.1fs, device_timeout=%.1fs, server_timeout=%.1fs)",
            self._check_interval,
            self._device_timeout,
            self._server_timeout,
        )
    
    def stop(self) -> None:
        """停止心跳监控"""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=self._check_interval * 2)
            self._thread = None
        logger.info("HeartbeatMonitor stopped")
    
    @property
    def is_running(self) -> bool:
        """检查监控是否运行中"""
        return self._thread is not None and self._thread.is_alive()
    
    def update_config(
        self,
        check_interval_s: float | None = None,
        device_timeout_s: float | None = None,
        server_timeout_s: float | None = None,
    ) -> None:
        """
        更新监控配置
        
        参数:
            check_interval_s: 检查间隔
            device_timeout_s: 设备超时
            server_timeout_s: 服务器超时
        """
        if check_interval_s is not None:
            self._check_interval = check_interval_s
        if device_timeout_s is not None:
            self._device_timeout = device_timeout_s
        if server_timeout_s is not None:
            self._server_timeout = server_timeout_s
    
    # ------------------------------------------------------------------
    #  内部循环
    # ------------------------------------------------------------------
    
    def _run_loop(self) -> None:
        """监控主循环"""
        while not self._stop_event.is_set():
            try:
                self._check_devices()
                self._check_servers()
            except Exception:
                logger.exception("HeartbeatMonitor check error")
            self._stop_event.wait(self._check_interval)
    
    def _check_devices(self) -> None:
        """检查设备心跳"""
        from models import DeviceStatus
        
        now = time.time()
        for device in self._manager.get_all_devices():
            if device.is_simulated:
                continue
            if device.status == DeviceStatus.OFFLINE:
                continue
            elapsed = now - device.last_active_time
            if elapsed > self._device_timeout:
                logger.warning(
                    "Device %s heartbeat timeout (%.1fs > %.1fs), marking offline",
                    device.device_id,
                    elapsed,
                    self._device_timeout,
                )
                self._manager.mark_device_offline(
                    device.device_id, reason="heartbeat_timeout"
                )
    
    def _check_servers(self) -> None:
        """检查服务器心跳"""
        from models import ServerStatus
        
        now = time.time()
        for server in self._manager.get_all_servers():
            if server.status == ServerStatus.OFFLINE:
                continue
            elapsed = now - server.last_heartbeat
            if elapsed > self._server_timeout:
                logger.warning(
                    "Server %s heartbeat timeout (%.1fs > %.1fs), marking offline",
                    server.server_id,
                    elapsed,
                    self._server_timeout,
                )
                self._manager.mark_server_offline(
                    server.server_id, reason="heartbeat_timeout"
                )
