"""
集中配置管理
支持自定义存储路径、心跳超时等参数
"""
import os
from pathlib import Path
from typing import Optional, Dict, Any


class Settings:
    """
    全局配置管理器（单例）
    
    提供以下功能：
    - 存储路径配置（任务、结果、遥测数据）
    - 心跳监控参数
    - 日志配置
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
        
        # 基础路径
        self.base_dir = Path(os.environ.get("CLOUD_EDGE_BASE_DIR", "."))
        self.data_dir = self.base_dir / "data"
        
        # 存储路径配置
        self.tasks_dir = self.data_dir / "tasks"
        self.results_dir = self.data_dir / "results"
        self.telemetry_dir = self.data_dir / "telemetry"
        self.logs_dir = self.data_dir / "logs"
        
        # 心跳监控参数
        self.heartbeat_check_interval_s = 5.0
        self.device_timeout_s = 15.0
        self.server_timeout_s = 30.0
        
        # 日志配置
        self.log_level = "INFO"
        self.log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        
        # 节点工厂配置（用于自动识别）
        self.auto_register_enabled = True
        self.auto_register_timeout_s = 60.0
        
        # 创建必要目录
        self._ensure_directories()
        
        self._initialized = True
    
    def _ensure_directories(self) -> None:
        """确保所有必要目录存在"""
        for directory in [self.tasks_dir, self.results_dir, self.telemetry_dir, self.logs_dir]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def set_base_dir(self, base_dir: str) -> None:
        """设置基础目录"""
        self.base_dir = Path(base_dir)
        self.data_dir = self.base_dir / "data"
        self.tasks_dir = self.data_dir / "tasks"
        self.results_dir = self.data_dir / "results"
        self.telemetry_dir = self.data_dir / "telemetry"
        self.logs_dir = self.data_dir / "logs"
        self._ensure_directories()
    
    def set_storage_paths(
        self,
        tasks_dir: Optional[str] = None,
        results_dir: Optional[str] = None,
        telemetry_dir: Optional[str] = None,
        logs_dir: Optional[str] = None,
    ) -> None:
        """
        自定义存储路径
        
        参数:
            tasks_dir: 任务记录存储目录
            results_dir: 计算结果存储目录
            telemetry_dir: 遥测数据存储目录
            logs_dir: 日志存储目录
        """
        if tasks_dir:
            self.tasks_dir = Path(tasks_dir)
        if results_dir:
            self.results_dir = Path(results_dir)
        if telemetry_dir:
            self.telemetry_dir = Path(telemetry_dir)
        if logs_dir:
            self.logs_dir = Path(logs_dir)
        self._ensure_directories()
    
    def set_heartbeat_config(
        self,
        check_interval_s: Optional[float] = None,
        device_timeout_s: Optional[float] = None,
        server_timeout_s: Optional[float] = None,
    ) -> None:
        """
        配置心跳监控参数
        
        参数:
            check_interval_s: 检查间隔（秒）
            device_timeout_s: 设备心跳超时（秒）
            server_timeout_s: 服务器心跳超时（秒）
        """
        if check_interval_s is not None:
            self.heartbeat_check_interval_s = check_interval_s
        if device_timeout_s is not None:
            self.device_timeout_s = device_timeout_s
        if server_timeout_s is not None:
            self.server_timeout_s = server_timeout_s
    
    def set_auto_register(self, enabled: bool, timeout_s: float = 60.0) -> None:
        """
        配置自动注册参数
        
        参数:
            enabled: 是否启用自动注册
            timeout_s: 自动注册超时（秒）
        """
        self.auto_register_enabled = enabled
        self.auto_register_timeout_s = timeout_s
    
    def to_dict(self) -> Dict[str, Any]:
        """导出配置为字典"""
        return {
            "base_dir": str(self.base_dir),
            "data_dir": str(self.data_dir),
            "tasks_dir": str(self.tasks_dir),
            "results_dir": str(self.results_dir),
            "telemetry_dir": str(self.telemetry_dir),
            "logs_dir": str(self.logs_dir),
            "heartbeat_check_interval_s": self.heartbeat_check_interval_s,
            "device_timeout_s": self.device_timeout_s,
            "server_timeout_s": self.server_timeout_s,
            "log_level": self.log_level,
            "auto_register_enabled": self.auto_register_enabled,
            "auto_register_timeout_s": self.auto_register_timeout_s,
        }


# 全局单例
settings = Settings()
