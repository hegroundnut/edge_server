"""
边缘服务器 uvaTrack 工具入口 — CTest 类
平台通过 ProcessTask 调用 subfuncs 中定义的方法，每个方法接收 params 字典。

架构变更:
  无人机不再直接连接边缘服务器，而是先连接类脑盒子（BrainBox），
  类脑盒子再将数据上报到边缘服务器。设备表与类脑盒子绑定。

  ┌────────────────┐     HTTP/POST     ┌──────────────┐     MAVLink      ┌──────────┐
  │  边缘控制服务   │ ◄──────────────► │  类脑盒子     │ ◄──────────────► │  无人机   │
  │  Edge Server   │                   │  BrainBox    │                   │  Drones  │
  └────────────────┘                   └──────────────┘                   └──────────┘

支持的子功能:

  类脑盒子管理:
    add_brain_box         注册类脑盒子实例到边缘服务器
    remove_brain_box      移除类脑盒子实例
    list_brain_boxes      获取已注册的类脑盒子列表
    get_brain_box_status  查询类脑盒子详细状态（远程调用）

  数据接收（类脑盒子 → 边缘服务器）:
    heartbeat             接收类脑盒子心跳上报
    drone_report          接收无人机状态上报
    trajectory_report     接收导航轨迹上报

  指令转发（边缘服务器 → 类脑盒子）:
    scan_drones           转发扫描指令到类脑盒子
    query_drones          转发查询指令到类脑盒子
    send_command          转发控制指令到类脑盒子

  导航任务:
    navigation_instruction  下发导航指令（经由类脑盒子到无人机）
    execute_trajectory      转发轨迹执行指令

  设备查询:
    list_devices          获取所有已知无人机设备列表
    get_device_info       获取设备详细信息
    list_tasks            查询导航任务列表

--- params JSON 格式示例 ---

add_brain_box:
{
    "box_id": "brain_box_001",
    "ip_address": "192.168.1.50",
    "port": 9000
}

remove_brain_box:
{
    "box_id": "brain_box_001"
}

list_brain_boxes:
{}

heartbeat (类脑盒子上报):
{
    "box_id": "brain_box_001",
    "timestamp": 1715340000.123,
    "status": "running",
    "drone_count": 3,
    "online_count": 3,
    "ip_address": "192.168.1.50",
    "port": 9000
}

drone_report (类脑盒子上报):
{
    "box_id": "brain_box_001",
    "timestamp": 1715340000.123,
    "devices": [
        {
            "device_id": "drone_sim_0",
            "device_type": "quadcopter",
            "protocol": "mavlink",
            "status": "online",
            "position": {"latitude": 39.9042, "longitude": 116.4074, "altitude": 100.0}
        }
    ]
}

trajectory_report (类脑盒子上报):
{
    "box_id": "brain_box_001",
    "timestamp": 1715340000.123,
    "trajectory": {
        "trajectory_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "device_id": "drone_sim_0",
        "waypoints": [...],
        "algorithm_name": "simple_linear",
        "total_distance": 1287.45,
        "estimated_time": 160.93
    }
}

scan_drones:
{
    "box_id": "brain_box_001"
}

query_drones:
{
    "box_id": "brain_box_001",
    "device_id": "drone_sim_0"
}

send_command:
{
    "box_id": "brain_box_001",
    "device_id": "drone_sim_0",
    "command": {
        "type": "takeoff",
        "altitude": 50.0
    }
}

navigation_instruction:
{
    "box_id": "brain_box_001",
    "instruction_id": "nav_20240510_001",
    "device_id": "drone_sim_0",
    "target_position": {
        "latitude": 39.91,
        "longitude": 116.42,
        "altitude": 120.0
    },
    "algorithm": "simple_linear",
    "parameters": {
        "step_count": 5,
        "speed": 8.0
    }
}

execute_trajectory:
{
    "box_id": "brain_box_001",
    "trajectory_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}

list_devices:
{
    "box_id": "all"
}

get_device_info:
{
    "device_id": "drone_sim_0"
}

list_tasks:
{
    "box_id": "all",
    "status": null,
    "limit": 100,
    "offset": 0
}

get_brain_box_status:
{
    "box_id": "brain_box_001"
}
"""
import os
import sys
import json
import logging

_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from core.manager import EdgeManager
from config.settings import settings
from utils.logger import setup_logging

logger = setup_logging("uvaTrack")


class CTest:
    """
    边缘服务器 uvaTrack 工具入口类。

    由平台框架通过 _load_train_version 自动实例化，
    每个公开方法对应 toolconfig.yml 中的一个 subfunc。
    """

    def __init__(self, node_cfg, process_comm, proc_modules_obj, progress_callback):
        self.node_cfg = node_cfg
        self.process_comm = process_comm
        self.proc_modules_obj = proc_modules_obj
        self.progress_callback = progress_callback

        heartbeat_cfg = node_cfg.get("heartbeat_config", {})

        settings.set_heartbeat_config(
            check_interval_s=heartbeat_cfg.get("check_interval_s"),
            box_timeout_s=heartbeat_cfg.get("box_timeout_s"),
        )

        request_timeout = node_cfg.get("request_timeout", 10.0)
        settings.set_request_timeout(request_timeout)

        logs_dir = node_cfg.get("logs_dir")
        if logs_dir:
            settings.logs_dir = logs_dir

        self._manager = EdgeManager(
            heartbeat_interval=settings.heartbeat_check_interval_s,
            box_timeout=settings.box_timeout_s,
            on_box_offline=self._on_box_offline_callback,
        )

    # ------------------------------------------------------------------
    #  回调
    # ------------------------------------------------------------------

    def _on_box_offline_callback(self, box):
        logger.warning(
            "BrainBox offline callback: box_id=%s", box.box_id,
        )

    # ------------------------------------------------------------------
    #  辅助
    # ------------------------------------------------------------------

    def _handle_result(self, func_name, result):
        print(func_name)
        print(result)
        if result.get("code", -1) == 0:
            self.progress_callback(
                100,
                json.dumps(result, ensure_ascii=False, default=str),
                "ok",
            )
        else:
            self.progress_callback(
                -1,
                json.dumps(result, ensure_ascii=False, default=str),
                "failed",
            )
        return result

    # ==================================================================
    #  类脑盒子管理
    # ==================================================================

    def add_brain_box(self, params):
        """注册类脑盒子实例到边缘服务器"""
        self.progress_callback(10, f"正在注册类脑盒子: {params.get('box_id')}")
        result = self._manager.add_brain_box(
            box_id=params["box_id"],
            ip_address=params["ip_address"],
            port=params.get("port", 9000),
            metadata=params.get("metadata", {}),
        )
        return self._handle_result("add_brain_box", result)

    def remove_brain_box(self, params):
        """移除类脑盒子实例"""
        self.progress_callback(10, f"正在移除类脑盒子: {params.get('box_id')}")
        result = self._manager.remove_brain_box(
            box_id=params["box_id"],
        )
        return self._handle_result("remove_brain_box", result)

    def list_brain_boxes(self, params):
        """获取已注册的类脑盒子列表"""
        self.progress_callback(10, "正在查询类脑盒子列表")
        result = self._manager.list_brain_boxes()
        return self._handle_result("list_brain_boxes", result)

    def get_brain_box_status(self, params):
        """查询类脑盒子详细状态（远程调用 brain_box 系统状态接口）"""
        box_id = params["box_id"]
        self.progress_callback(10, f"正在查询类脑盒子状态: {box_id}")
        result = self._manager.get_brain_box_status(box_id)
        return self._handle_result("get_brain_box_status", result)

    # ==================================================================
    #  数据接收（类脑盒子 → 边缘服务器）
    # ==================================================================

    def heartbeat(self, params):
        """接收类脑盒子心跳上报"""
        box_id = params.get("box_id", "")
        self.progress_callback(10, f"心跳上报: {box_id}")
        result = self._manager.receive_heartbeat(params)
        return self._handle_result("heartbeat", result)

    def drone_report(self, params):
        """接收无人机状态上报"""
        box_id = params.get("box_id", "")
        self.progress_callback(10, f"无人机状态上报: {box_id}")
        result = self._manager.receive_drone_report(params)
        return self._handle_result("drone_report", result)

    def trajectory_report(self, params):
        """接收导航轨迹上报"""
        box_id = params.get("box_id", "")
        self.progress_callback(10, f"轨迹上报: {box_id}")
        result = self._manager.receive_trajectory_report(params)
        return self._handle_result("trajectory_report", result)

    # ==================================================================
    #  指令转发（边缘服务器 → 类脑盒子）
    # ==================================================================

    def scan_drones(self, params):
        """转发扫描指令到指定类脑盒子"""
        box_id = params["box_id"]
        self.progress_callback(10, f"正在扫描无人机 (brain_box={box_id})")
        result = self._manager.forward_scan_drones(box_id)
        return self._handle_result("scan_drones", result)

    def query_drones(self, params):
        """转发查询指令到指定类脑盒子"""
        box_id = params["box_id"]
        query = {k: v for k, v in params.items() if k != "box_id"}
        self.progress_callback(10, f"正在查询无人机 (brain_box={box_id})")
        result = self._manager.forward_query_drones(box_id, query or None)
        return self._handle_result("query_drones", result)

    def send_command(self, params):
        """转发控制指令到指定类脑盒子"""
        box_id = params["box_id"]
        device_id = params["device_id"]
        command = params["command"]
        self.progress_callback(
            10, f"正在发送指令 (brain_box={box_id}, device={device_id})"
        )
        result = self._manager.forward_command(box_id, device_id, command)
        return self._handle_result("send_command", result)

    # ==================================================================
    #  导航任务
    # ==================================================================

    def navigation_instruction(self, params):
        """下发导航指令（经由类脑盒子到无人机）"""
        box_id = params.get("box_id", "")
        device_id = params.get("device_id", "")
        self.progress_callback(
            10, f"正在下发导航指令 (brain_box={box_id}, device={device_id})"
        )
        result = self._manager.send_navigation_instruction(params)
        return self._handle_result("navigation_instruction", result)

    def execute_trajectory(self, params):
        """转发轨迹执行指令到类脑盒子"""
        box_id = params.get("box_id", "")
        trajectory_id = params.get("trajectory_id", "")
        self.progress_callback(
            10, f"正在执行轨迹 (brain_box={box_id}, trajectory={trajectory_id})"
        )
        result = self._manager.execute_trajectory(params)
        return self._handle_result("execute_trajectory", result)

    # ==================================================================
    #  设备查询
    # ==================================================================

    def list_devices(self, params):
        """获取所有已知无人机设备列表"""
        box_id = params.get("box_id", "all")
        self.progress_callback(10, "正在查询设备列表")
        result = self._manager.list_devices(box_id=box_id)
        return self._handle_result("list_devices", result)

    def get_device_info(self, params):
        """获取设备详细信息"""
        device_id = params["device_id"]
        self.progress_callback(10, f"查询设备详情: {device_id}")
        info = self._manager.get_device_info(device_id)
        if info is None:
            result = {"code": -1, "msg": f"设备 {device_id} 不存在", "data": {}}
        else:
            result = {"code": 0, "msg": "success", "data": info}
        return self._handle_result("get_device_info", result)

    def list_tasks(self, params):
        """查询导航任务列表"""
        box_id = params.get("box_id", "all")
        status = params.get("status")
        limit = params.get("limit", 100)
        offset = params.get("offset", 0)
        self.progress_callback(10, "正在查询任务列表")
        result = self._manager.list_tasks(
            box_id=box_id, status=status, limit=limit, offset=offset,
        )
        return self._handle_result("list_tasks", result)
