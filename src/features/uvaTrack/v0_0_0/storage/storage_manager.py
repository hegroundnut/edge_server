"""
存储管理器抽象接口
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class StorageManager(ABC):
    """
    存储管理器抽象基类
    
    定义存储操作的通用接口，支持多种存储后端（本地文件、数据库等）。
    """
    
    @abstractmethod
    def save_task(self, task_id: str, task_data: Dict[str, Any]) -> bool:
        """保存任务记录"""
        pass
    
    @abstractmethod
    def load_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """加载任务记录"""
        pass
    
    @abstractmethod
    def list_tasks(self, device_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出任务记录"""
        pass
    
    @abstractmethod
    def save_result(self, result_id: str, result_data: Dict[str, Any]) -> bool:
        """保存计算结果"""
        pass
    
    @abstractmethod
    def load_result(self, result_id: str) -> Optional[Dict[str, Any]]:
        """加载计算结果"""
        pass
    
    @abstractmethod
    def list_results(self, task_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出计算结果"""
        pass
    
    @abstractmethod
    def save_telemetry(self, device_id: str, telemetry_data: Dict[str, Any]) -> bool:
        """保存遥测数据"""
        pass
    
    @abstractmethod
    def load_telemetry(self, device_id: str) -> Optional[Dict[str, Any]]:
        """加载最新遥测数据"""
        pass
    
    @abstractmethod
    def list_telemetry(self, device_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """列出遥测数据历史"""
        pass
