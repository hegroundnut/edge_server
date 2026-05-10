"""
集中配置管理
"""
import os
from pathlib import Path
from typing import Dict, Any


class Settings:
    """
    全局配置管理器（单例）

    配置项:
    - 心跳监控参数 (brain_box 心跳)
    - HTTP 请求超时
    - 日志配置
    - 数据存储路径
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.base_dir = Path(os.environ.get("EDGE_SERVER_BASE_DIR", "."))
        self.data_dir = self.base_dir / "data"
        self.logs_dir = self.data_dir / "logs"

        self.heartbeat_check_interval_s = 10.0
        self.box_timeout_s = 30.0
        self.request_timeout = 10.0

        self.log_level = "INFO"
        self.log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

        self._ensure_directories()
        self._initialized = True

    def _ensure_directories(self) -> None:
        for directory in [self.data_dir, self.logs_dir]:
            directory.mkdir(parents=True, exist_ok=True)

    def set_heartbeat_config(
        self,
        check_interval_s=None,
        box_timeout_s=None,
    ) -> None:
        if check_interval_s is not None:
            self.heartbeat_check_interval_s = check_interval_s
        if box_timeout_s is not None:
            self.box_timeout_s = box_timeout_s

    def set_request_timeout(self, timeout: float) -> None:
        self.request_timeout = timeout

    def to_dict(self) -> Dict[str, Any]:
        return {
            "base_dir": str(self.base_dir),
            "data_dir": str(self.data_dir),
            "logs_dir": str(self.logs_dir),
            "heartbeat_check_interval_s": self.heartbeat_check_interval_s,
            "box_timeout_s": self.box_timeout_s,
            "request_timeout": self.request_timeout,
            "log_level": self.log_level,
        }


settings = Settings()
