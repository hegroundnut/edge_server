"""
心跳监控守护线程
定期检查所有已注册的类脑盒子的活跃状态，
若超时未收到心跳则自动标记为离线。
"""
import time
import threading
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .manager import EdgeManager

logger = logging.getLogger(__name__)


class HeartbeatMonitor:
    """
    心跳监控器

    参数:
        manager: EdgeManager 实例
        check_interval_s: 检查间隔（秒），默认 10s
        box_timeout_s: 类脑盒子心跳超时（秒），默认 30s
    """

    def __init__(
        self,
        manager: "EdgeManager",
        check_interval_s: float = 10.0,
        box_timeout_s: float = 30.0,
    ):
        self._manager = manager
        self._check_interval = check_interval_s
        self._box_timeout = box_timeout_s
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop, name="heartbeat-monitor", daemon=True
        )
        self._thread.start()
        logger.info(
            "HeartbeatMonitor started (interval=%.1fs, box_timeout=%.1fs)",
            self._check_interval,
            self._box_timeout,
        )

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=self._check_interval * 2)
            self._thread = None
        logger.info("HeartbeatMonitor stopped")

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._check_brain_boxes()
            except Exception:
                logger.exception("HeartbeatMonitor check error")
            self._stop_event.wait(self._check_interval)

    def _check_brain_boxes(self) -> None:
        from models import BrainBoxStatus

        now = time.time()
        for box in self._manager.get_all_brain_boxes():
            if box.status == BrainBoxStatus.OFFLINE:
                continue
            elapsed = now - box.last_heartbeat
            if elapsed > self._box_timeout:
                logger.warning(
                    "BrainBox %s heartbeat timeout (%.1fs > %.1fs), marking offline",
                    box.box_id,
                    elapsed,
                    self._box_timeout,
                )
                self._manager.mark_brain_box_offline(
                    box.box_id, reason="heartbeat_timeout"
                )
