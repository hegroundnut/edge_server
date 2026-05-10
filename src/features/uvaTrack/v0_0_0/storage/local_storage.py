"""
本地文件存储实现
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from .storage_manager import StorageManager
from config.settings import settings

logger = logging.getLogger(__name__)


class LocalStorage(StorageManager):
    """
    本地文件系统存储实现
    
    将任务、结果、遥测数据存储为 JSON 文件，支持按日期和 ID 组织。
    """
    
    def __init__(self):
        """初始化本地存储"""
        self.tasks_dir = settings.tasks_dir
        self.results_dir = settings.results_dir
        self.telemetry_dir = settings.telemetry_dir
        
        # 确保目录存在
        for directory in [self.tasks_dir, self.results_dir, self.telemetry_dir]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def _get_task_path(self, task_id: str) -> Path:
        """获取任务文件路径"""
        return self.tasks_dir / f"{task_id}.json"
    
    def _get_result_path(self, result_id: str) -> Path:
        """获取结果文件路径"""
        return self.results_dir / f"{result_id}.json"
    
    def _get_telemetry_path(self, device_id: str, index: int = 0) -> Path:
        """获取遥测文件路径"""
        device_dir = self.telemetry_dir / device_id
        device_dir.mkdir(parents=True, exist_ok=True)
        return device_dir / f"telemetry_{index:06d}.json"
    
    def save_task(self, task_id: str, task_data: Dict[str, Any]) -> bool:
        """保存任务记录"""
        try:
            path = self._get_task_path(task_id)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(task_data, f, ensure_ascii=False, indent=2, default=str)
            logger.info(f"Task saved: {task_id} -> {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save task {task_id}: {e}")
            return False
    
    def load_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """加载任务记录"""
        try:
            path = self._get_task_path(task_id)
            if not path.exists():
                return None
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load task {task_id}: {e}")
            return None
    
    def list_tasks(self, device_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出任务记录"""
        try:
            tasks = []
            for task_file in self.tasks_dir.glob("*.json"):
                try:
                    with open(task_file, "r", encoding="utf-8") as f:
                        task = json.load(f)
                        if device_id is None or task.get("device_id") == device_id:
                            tasks.append(task)
                except Exception as e:
                    logger.warning(f"Failed to read task file {task_file}: {e}")
            return tasks
        except Exception as e:
            logger.error(f"Failed to list tasks: {e}")
            return []
    
    def save_result(self, result_id: str, result_data: Dict[str, Any]) -> bool:
        """保存计算结果"""
        try:
            path = self._get_result_path(result_id)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2, default=str)
            logger.info(f"Result saved: {result_id} -> {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save result {result_id}: {e}")
            return False
    
    def load_result(self, result_id: str) -> Optional[Dict[str, Any]]:
        """加载计算结果"""
        try:
            path = self._get_result_path(result_id)
            if not path.exists():
                return None
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load result {result_id}: {e}")
            return None
    
    def list_results(self, task_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出计算结果"""
        try:
            results = []
            for result_file in self.results_dir.glob("*.json"):
                try:
                    with open(result_file, "r", encoding="utf-8") as f:
                        result = json.load(f)
                        if task_id is None or result.get("task_id") == task_id:
                            results.append(result)
                except Exception as e:
                    logger.warning(f"Failed to read result file {result_file}: {e}")
            return results
        except Exception as e:
            logger.error(f"Failed to list results: {e}")
            return []
    
    def save_telemetry(self, device_id: str, telemetry_data: Dict[str, Any]) -> bool:
        """保存遥测数据"""
        try:
            # 找到下一个可用的索引
            device_dir = self.telemetry_dir / device_id
            device_dir.mkdir(parents=True, exist_ok=True)
            
            # 获取现有文件数量作为下一个索引
            existing_files = list(device_dir.glob("telemetry_*.json"))
            index = len(existing_files)
            
            path = device_dir / f"telemetry_{index:06d}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(telemetry_data, f, ensure_ascii=False, indent=2, default=str)
            logger.debug(f"Telemetry saved: {device_id} -> {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save telemetry for {device_id}: {e}")
            return False
    
    def load_telemetry(self, device_id: str) -> Optional[Dict[str, Any]]:
        """加载最新遥测数据"""
        try:
            device_dir = self.telemetry_dir / device_id
            if not device_dir.exists():
                return None
            
            # 获取最新的文件
            files = sorted(device_dir.glob("telemetry_*.json"))
            if not files:
                return None
            
            latest_file = files[-1]
            with open(latest_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load telemetry for {device_id}: {e}")
            return None
    
    def list_telemetry(self, device_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """列出遥测数据历史"""
        try:
            device_dir = self.telemetry_dir / device_id
            if not device_dir.exists():
                return []
            
            telemetry_list = []
            files = sorted(device_dir.glob("telemetry_*.json"), reverse=True)[:limit]
            
            for telemetry_file in files:
                try:
                    with open(telemetry_file, "r", encoding="utf-8") as f:
                        telemetry = json.load(f)
                        telemetry_list.append(telemetry)
                except Exception as e:
                    logger.warning(f"Failed to read telemetry file {telemetry_file}: {e}")
            
            return telemetry_list
        except Exception as e:
            logger.error(f"Failed to list telemetry for {device_id}: {e}")
            return []
