"""
数据库操作抽象接口

所有持久化操作通过 BaseRepository 定义，
具体数据库实现（SQLite / PostgreSQL 等）只需实现此接口。
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class BaseRepository(ABC):
    """数据持久化抽象接口"""

    # ------------------------------------------------------------------
    #  生命周期
    # ------------------------------------------------------------------

    @abstractmethod
    def initialize(self) -> None:
        """初始化数据库连接和表结构"""

    @abstractmethod
    def close(self) -> None:
        """关闭数据库连接"""

    # ------------------------------------------------------------------
    #  导航任务 (NavigationTask)
    # ------------------------------------------------------------------

    @abstractmethod
    def save_task(self, task_dict: Dict[str, Any]) -> None:
        """保存或更新任务"""

    @abstractmethod
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """按 task_id 获取任务"""

    @abstractmethod
    def list_tasks(
        self,
        box_id: str = "all",
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """查询任务列表"""

    @abstractmethod
    def count_tasks(self, box_id: str = "all", status: Optional[str] = None) -> int:
        """统计任务数量"""

    @abstractmethod
    def update_task(self, task_id: str, **fields) -> bool:
        """更新任务字段（部分更新）"""

    @abstractmethod
    def find_task_by_trajectory(self, trajectory_id: str) -> Optional[Dict[str, Any]]:
        """按 trajectory_id 查找任务"""

    @abstractmethod
    def find_pending_task(self, box_id: str, device_id: str) -> Optional[Dict[str, Any]]:
        """查找指定 box_id + device_id 下处于 pending/executing 状态的任务"""

    # ------------------------------------------------------------------
    #  无人机设备 (DroneDevice)
    # ------------------------------------------------------------------

    @abstractmethod
    def save_device(self, device_dict: Dict[str, Any]) -> None:
        """保存或更新设备"""

    @abstractmethod
    def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """按 device_id 获取设备"""

    @abstractmethod
    def list_devices(self, box_id: str = "all") -> List[Dict[str, Any]]:
        """获取设备列表"""

    @abstractmethod
    def delete_devices_by_box(self, box_id: str) -> int:
        """删除指定 brain_box 下的所有设备，返回删除数量"""

    @abstractmethod
    def update_device_status_by_box(self, box_id: str, status: str) -> int:
        """批量更新指定 brain_box 下的设备状态"""

    # ------------------------------------------------------------------
    #  心跳日志 (HeartbeatLog)
    # ------------------------------------------------------------------

    @abstractmethod
    def save_heartbeat_log(self, log_dict: Dict[str, Any]) -> None:
        """保存心跳日志"""

    @abstractmethod
    def list_heartbeat_logs(
        self,
        box_id: str = "all",
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """查询心跳日志"""

    @abstractmethod
    def cleanup_heartbeat_logs(self, older_than_timestamp: float) -> int:
        """清理指定时间戳之前的心跳日志，返回删除数量"""
