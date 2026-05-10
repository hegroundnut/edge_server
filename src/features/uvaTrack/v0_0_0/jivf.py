"""
CloudEdgeManager 工具入口 — CTest 类
平台通过 ProcessTask 调用 subfuncs 中定义的方法，每个方法接收 params 字典。

支持的子功能:
  add_server          注册计算服务器节点到云端调度池
  remove_server       从调度池中安全移除指定服务器
  list_servers        获取可用的计算服务器列表及当前负载状态
  add_device          注册边缘设备（如机器狗、无人车）到管控系统
  remove_device       从系统中注销边缘设备
  list_devices        获取已注册的边缘设备列表及在线状态
  assign_and_start_task  核心调度：指定边缘设备连接特定服务器执行计算任务
  stop_task           中断指定设备与服务器之间的任务和数据流

扩展接口:
  heartbeat           设备/服务器心跳上报（支持自动识别和添加）
  get_device_info     获取设备详细信息（含流通道、遥测）
  get_task_info       查询任务详情（含计算结果）
  update_location     设备位置上报

通用数据交互接口:
  submit_task_result       服务器提交任务计算结果（类型+载荷由调用方定义）
  update_device_telemetry  设备/服务器上报遥测数据（类型+数据由调用方定义）

--- params JSON 格式示例 ---

add_server:
{
    "server_id": "svr_node_01",
    "ip_address": "192.168.1.100",
    "capacity": 5,
    "tags": ["gpu", "path_planning"]
}

remove_server:
{
    "server_id": "svr_node_01",
    "force_stop": true
}

list_servers:
{
    "filter_by_status": "active"
}

add_device:
{
    "device_id": "robot_dog_nx_01",
    "hardware_type": "jetson_xavier_nx",
    "is_simulated": false,
    "supported_streams": ["video", "lidar_point_cloud"]
}

remove_device:
{
    "device_id": "robot_dog_nx_01"
}

list_devices:
{
    "group_id": "all"
}

assign_and_start_task:
{
    "device_id": "robot_dog_nx_01",
    "server_id": "svr_node_01",
    "task_config": {
        "algorithm": "a_star_optimized",
        "frequency_hz": 10,
        "enable_video_stream": true,
        "stream_port": 8554,
        "custom_payloads": {
            "map_resolution": 0.05,
            "enable_local_slm": true,
            "start_point": {"lat": 30.27, "lng": 120.15, "alt": 10.0},
            "end_point": {"lat": 30.28, "lng": 120.16, "alt": 10.0},
            "nav_params": {"obstacle_avoidance": true, "max_speed_m_s": 5.0}
        }
    }
}

stop_task:
{
    "device_id": "robot_dog_nx_01",
    "reason": "user_manual_stop"
}

heartbeat (设备自动注册示例):
{
    "target_type": "device",
    "target_id": "robot_dog_nx_01",
    "location": {"lat": 30.27, "lng": 120.15, "alt": 5.0},
    "metadata": {
        "hardware_type": "jetson_xavier_nx",
        "supported_streams": ["video", "lidar_point_cloud"]
    }
}

heartbeat (服务器):
{
    "target_type": "server",
    "target_id": "svr_node_01"
}

get_device_info:
{
    "device_id": "robot_dog_nx_01"
}

get_task_info:
{
    "task_id": "task_a1b2c3d4e5f6"
}

update_location:
{
    "device_id": "robot_dog_nx_01",
    "location": {"lat": 30.27, "lng": 120.15, "alt": 5.0}
}

submit_task_result:
{
    "task_id": "task_a1b2c3d4e5f6",
    "result_type": "trajectory",
    "payload": {
        "waypoints": [
            {"lat": 30.270, "lng": 120.150, "alt": 10.0, "seq": 0, "speed_m_s": 3.0},
            {"lat": 30.275, "lng": 120.155, "alt": 10.0, "seq": 1, "speed_m_s": 5.0},
            {"lat": 30.280, "lng": 120.160, "alt": 10.0, "seq": 2, "speed_m_s": 3.0}
        ],
        "total_distance_m": 1200.5,
        "estimated_time_s": 240.0,
        "algorithm_used": "a_star_optimized"
    },
    "metadata": {"source": "brain_box_01"}
}

update_device_telemetry:
{
    "device_id": "robot_dog_nx_01",
    "telemetry_type": "drone_status",
    "data": {
        "position": {"lat": 30.271, "lng": 120.151, "alt": 10.2},
        "velocity": {"vx": 1.2, "vy": 0.5, "vz": 0.0},
        "attitude": {"roll": 0.01, "pitch": -0.02, "yaw": 1.57},
        "battery_pct": 85.0,
        "flight_mode": "GUIDED",
        "armed": true,
        "gps_fix_type": 3,
        "satellites_visible": 12
    },
    "metadata": {"source": "mavlink"}
}
"""
import os
import sys
import json
import logging

_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from core.manager import CloudEdgeManager
from config.settings import settings
from utils.logger import setup_logging

logger = setup_logging("uvaTrack")


class CTest:
    """
    云边协同管控工具入口类。

    由平台框架通过 _load_train_version 自动实例化，
    每个公开方法对应 toolconfig.yml 中的一个 subfunc。
    """

    def __init__(self, node_cfg, process_comm, proc_modules_obj, progress_callback):
        self.node_cfg = node_cfg
        self.process_comm = process_comm
        self.proc_modules_obj = proc_modules_obj
        self.progress_callback = progress_callback

        # 从配置中读取参数
        heartbeat_cfg = node_cfg.get("heartbeat_config", {})
        storage_cfg = node_cfg.get("storage_config", {})
        
        # 配置存储路径
        if storage_cfg:
            settings.set_storage_paths(
                tasks_dir=storage_cfg.get("tasks_dir"),
                results_dir=storage_cfg.get("results_dir"),
                telemetry_dir=storage_cfg.get("telemetry_dir"),
                logs_dir=storage_cfg.get("logs_dir"),
            )
        
        # 配置心跳参数
        settings.set_heartbeat_config(
            check_interval_s=heartbeat_cfg.get("check_interval_s"),
            device_timeout_s=heartbeat_cfg.get("device_timeout_s"),
            server_timeout_s=heartbeat_cfg.get("server_timeout_s"),
        )
        
        # 配置自动注册
        auto_register_cfg = node_cfg.get("auto_register_config", {})
        if auto_register_cfg:
            settings.set_auto_register(
                enabled=auto_register_cfg.get("enabled", True),
                timeout_s=auto_register_cfg.get("timeout_s", 60.0),
            )
        
        # 初始化管理器
        self._manager = CloudEdgeManager(
            heartbeat_interval=settings.heartbeat_check_interval_s,
            device_timeout=settings.device_timeout_s,
            server_timeout=settings.server_timeout_s,
            on_task_stopped=self._on_task_stopped_callback,
        )

    # ------------------------------------------------------------------
    #  回调
    # ------------------------------------------------------------------

    def _on_task_stopped_callback(self, task):
        logger.info(
            "Task stopped callback: task_id=%s reason=%s",
            task.task_id,
            task.stop_reason,
        )

    # ------------------------------------------------------------------
    #  辅助：统一结果处理
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
    #  服务器管理
    # ==================================================================

    def add_server(self, params):
        """注册计算服务器节点到云端调度池"""
        self.progress_callback(10, f"正在注册服务器: {params.get('server_id')}")
        result = self._manager.add_server(
            server_id=params["server_id"],
            ip_address=params["ip_address"],
            capacity=params.get("capacity", 10),
            tags=params.get("tags", []),
            metadata=params.get("metadata", {}),
        )
        return self._handle_result("add_server", result)

    def remove_server(self, params):
        """从调度池中安全移除指定的服务器"""
        self.progress_callback(10, f"正在移除服务器: {params.get('server_id')}")
        result = self._manager.remove_server(
            server_id=params["server_id"],
            force_stop=bool(params.get("force_stop", False)),
        )
        return self._handle_result("remove_server", result)

    def list_servers(self, params):
        """获取可用的计算服务器列表及当前负载状态"""
        self.progress_callback(10, "正在查询服务器列表")
        result = self._manager.list_servers(
            filter_by_status=params.get("filter_by_status", "all"),
        )
        return self._handle_result("list_servers", result)

    # ==================================================================
    #  设备管理
    # ==================================================================

    def add_device(self, params):
        """注册边缘设备到管控系统"""
        self.progress_callback(10, f"正在注册设备: {params.get('device_id')}")
        result = self._manager.add_device(
            device_id=params["device_id"],
            hardware_type=params["hardware_type"],
            is_simulated=bool(params.get("is_simulated", False)),
            supported_streams=params.get("supported_streams", []),
            group_id=params.get("group_id", "default"),
            metadata=params.get("metadata", {}),
        )
        return self._handle_result("add_device", result)

    def remove_device(self, params):
        """从系统中注销边缘设备"""
        self.progress_callback(10, f"正在注销设备: {params.get('device_id')}")
        result = self._manager.remove_device(
            device_id=params["device_id"],
        )
        return self._handle_result("remove_device", result)

    def list_devices(self, params):
        """获取已注册的边缘设备列表及在线状态"""
        self.progress_callback(10, "正在查询设备列表")
        result = self._manager.list_devices(
            group_id=params.get("group_id", "all"),
        )
        return self._handle_result("list_devices", result)

    # ==================================================================
    #  核心调度
    # ==================================================================

    def assign_and_start_task(self, params):
        """核心调度：指定边缘设备连接特定服务器执行计算任务"""
        device_id = params["device_id"]
        server_id = params["server_id"]
        self.progress_callback(
            10,
            f"正在调度: 设备 {device_id} -> 服务器 {server_id}",
        )
        result = self._manager.assign_and_start_task(
            device_id=device_id,
            server_id=server_id,
            task_config=params.get("task_config", {}),
        )
        return self._handle_result("assign_and_start_task", result)

    def stop_task(self, params):
        """中断指定设备与服务器之间的任务和数据流"""
        device_id = params["device_id"]
        self.progress_callback(10, f"正在停止设备 {device_id} 的任务")
        result = self._manager.stop_task(
            device_id=device_id,
            reason=params.get("reason", "user_manual_stop"),
        )
        return self._handle_result("stop_task", result)

    # ==================================================================
    #  扩展接口
    # ==================================================================

    def heartbeat(self, params):
        """
        设备/服务器心跳上报
        
        支持自动识别和添加陌生设备/服务器。
        心跳消息中的 metadata 字段应包含必要的注册信息。
        """
        target_type = params.get("target_type", "device")
        target_id = params.get("target_id", "")
        location = params.get("location")

        self.progress_callback(10, f"心跳上报: {target_type}/{target_id}")

        if target_type == "device":
            ok = self._manager.refresh_device_heartbeat(
                target_id,
                location=location,
                heartbeat_data=params,  # 传递完整心跳数据用于自动注册
            )
        elif target_type == "server":
            ok = self._manager.refresh_server_heartbeat(target_id)
        else:
            result = {"code": -1, "msg": f"未知目标类型: {target_type}", "data": {}}
            return self._handle_result("heartbeat", result)

        result = {
            "code": 0 if ok else -1,
            "msg": "success" if ok else f"{target_type} {target_id} 不存在或已被移除",
            "data": {"target_type": target_type, "target_id": target_id},
        }
        return self._handle_result("heartbeat", result)

    def get_device_info(self, params):
        """获取设备详细信息（含流通道、当前任务和最新遥测）"""
        device_id = params["device_id"]
        self.progress_callback(10, f"查询设备详情: {device_id}")
        info = self._manager.get_device_info(device_id)
        if info is None:
            result = {"code": -1, "msg": f"设备 {device_id} 不存在", "data": {}}
        else:
            result = {"code": 0, "msg": "success", "data": info}
        return self._handle_result("get_device_info", result)

    def get_task_info(self, params):
        """查询任务详情（含计算结果列表）"""
        task_id = params["task_id"]
        self.progress_callback(10, f"查询任务详情: {task_id}")
        info = self._manager.get_task_info(task_id)
        if info is None:
            result = {"code": -1, "msg": f"任务 {task_id} 不存在", "data": {}}
        else:
            result = {"code": 0, "msg": "success", "data": info}
        return self._handle_result("get_task_info", result)

    def update_location(self, params):
        """设备位置上报"""
        device_id = params["device_id"]
        location = params.get("location", {})
        self.progress_callback(10, f"位置上报: {device_id}")
        ok = self._manager.refresh_device_heartbeat(device_id, location=location)
        result = {
            "code": 0 if ok else -1,
            "msg": "success" if ok else f"设备 {device_id} 不存在",
            "data": {"device_id": device_id, "location": location},
        }
        return self._handle_result("update_location", result)

    # ==================================================================
    #  通用数据交互接口
    # ==================================================================

    def submit_task_result(self, params):
        """服务器提交任务计算结果（通用，result_type 标识结果类型）"""
        task_id = params["task_id"]
        result_type = params.get("result_type", "")
        self.progress_callback(10, f"提交任务结果: task={task_id} type={result_type}")
        result = self._manager.submit_task_result(
            task_id=task_id,
            result_type=result_type,
            payload=params.get("payload", {}),
            metadata=params.get("metadata", {}),
        )
        return self._handle_result("submit_task_result", result)

    def update_device_telemetry(self, params):
        """设备/服务器上报遥测数据（通用，telemetry_type 标识遥测类型）"""
        device_id = params["device_id"]
        telemetry_type = params.get("telemetry_type", "")
        self.progress_callback(
            10, f"遥测上报: device={device_id} type={telemetry_type}"
        )
        result = self._manager.update_device_telemetry(
            device_id=device_id,
            telemetry_type=telemetry_type,
            data=params.get("data", {}),
            metadata=params.get("metadata", {}),
        )
        return self._handle_result("update_device_telemetry", result)
