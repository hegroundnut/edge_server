"""
导航任务模型
"""
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from .base import NavigationStatus


@dataclass
class NavigationTask:
    """
    导航任务记录

    属性:
        task_id: 任务唯一标识
        instruction_id: 导航指令 ID
        box_id: 执行任务的类脑盒子 ID
        device_id: 目标无人机设备 ID
        target_position: 目标位置
        algorithm: 导航算法
        parameters: 算法参数
        status: 任务状态
        trajectory_id: 生成的轨迹 ID (由 brain_box 返回)
        created_at: 创建时间戳
        completed_at: 完成时间戳
        result: 任务结果数据
    """
    task_id: str
    instruction_id: str
    box_id: str
    device_id: str
    target_position: Dict[str, float] = field(default_factory=dict)
    algorithm: str = "simple_linear"
    parameters: Dict[str, Any] = field(default_factory=dict)
    status: NavigationStatus = NavigationStatus.PENDING
    trajectory_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    result: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "instruction_id": self.instruction_id,
            "box_id": self.box_id,
            "device_id": self.device_id,
            "target_position": dict(self.target_position),
            "algorithm": self.algorithm,
            "parameters": dict(self.parameters),
            "status": self.status.value,
            "trajectory_id": self.trajectory_id,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "result": dict(self.result),
        }

    @staticmethod
    def generate_task_id() -> str:
        return f"nav_{uuid.uuid4().hex[:12]}"
