"""
日志工具
"""
import logging
import logging.handlers
from pathlib import Path
from config.settings import settings


def setup_logging(name: str = "cloud_edge_manager") -> logging.Logger:
    """
    配置日志系统
    
    参数:
        name: 日志记录器名称
    
    返回:
        配置好的日志记录器
    """
    logger = logging.getLogger(name)
    
    # 避免重复添加处理器
    if logger.handlers:
        return logger
    
    logger.setLevel(getattr(logging, settings.log_level))
    
    # 创建日志目录
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    
    # 文件处理器
    log_file = settings.logs_dir / f"{name}.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(getattr(logging, settings.log_level))
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, settings.log_level))
    
    # 格式化器
    formatter = logging.Formatter(settings.log_format)
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加处理器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger
