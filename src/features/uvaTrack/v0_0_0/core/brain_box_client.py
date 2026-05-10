"""
类脑盒子 HTTP 客户端 — 所有请求使用 POST
参考 brain_box 的 API 接口，将边缘服务器的指令转发给类脑盒子。
"""
import logging
from typing import Dict, Any, Optional
import urllib.request
import urllib.error
import json

logger = logging.getLogger(__name__)


class BrainBoxClient:
    """
    类脑盒子 HTTP 客户端

    向指定的 brain_box 实例发送 POST 请求，
    路径与 brain_box API 一致。
    """

    def __init__(self, timeout: float = 10.0):
        self._timeout = timeout

    def _post(self, base_url: str, path: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """统一 POST 请求"""
        url = f"{base_url}{path}"
        body = json.dumps(data or {}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                result: Dict[str, Any] = json.loads(resp.read().decode("utf-8"))
                logger.debug("POST %s 成功: %s", url, resp.status)
                return result
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", errors="replace")
            logger.error("POST %s 失败: %s - %s", url, e.code, body_text)
            return {"success": False, "error": body_text, "status_code": e.code}
        except urllib.error.URLError as e:
            logger.error("POST %s 连接异常: %s", url, e.reason)
            return {"success": False, "error": str(e.reason)}
        except Exception as e:
            logger.error("POST %s 请求异常: %s", url, e)
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    #  无人机管理
    # ------------------------------------------------------------------

    def scan_drones(self, base_url: str) -> Dict[str, Any]:
        """扫描网络中的无人机"""
        return self._post(base_url, "/api/v1/drones/scan")

    def query_drones(self, base_url: str, query: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """查询无人机信息"""
        return self._post(base_url, "/api/v1/drones/query", query)

    def drones_summary(self, base_url: str) -> Dict[str, Any]:
        """获取无人机汇总"""
        return self._post(base_url, "/api/v1/drones/summary")

    def send_command(self, base_url: str, device_id: str, command: Dict[str, Any]) -> Dict[str, Any]:
        """向指定无人机发送控制指令"""
        return self._post(base_url, "/api/v1/drones/command", {
            "device_id": device_id,
            "command": command,
        })

    # ------------------------------------------------------------------
    #  导航
    # ------------------------------------------------------------------

    def navigation_instruction(
        self,
        base_url: str,
        instruction_id: str,
        device_id: str,
        target_position: Dict[str, float],
        algorithm: str = "simple_linear",
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """下发导航指令"""
        return self._post(base_url, "/api/v1/navigation/instruction", {
            "instruction_id": instruction_id,
            "device_id": device_id,
            "target_position": target_position,
            "algorithm": algorithm,
            "parameters": parameters or {},
        })

    def execute_trajectory(self, base_url: str, trajectory_id: str) -> Dict[str, Any]:
        """执行导航轨迹"""
        return self._post(base_url, "/api/v1/navigation/execute", {
            "trajectory_id": trajectory_id,
        })

    def list_trajectories(self, base_url: str) -> Dict[str, Any]:
        """查看活动轨迹"""
        return self._post(base_url, "/api/v1/navigation/trajectories")

    def list_algorithms(self, base_url: str) -> Dict[str, Any]:
        """列出可用算法"""
        return self._post(base_url, "/api/v1/navigation/algorithms")

    # ------------------------------------------------------------------
    #  系统
    # ------------------------------------------------------------------

    def system_status(self, base_url: str) -> Dict[str, Any]:
        """获取系统状态"""
        return self._post(base_url, "/api/v1/system/status")
