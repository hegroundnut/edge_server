#!/usr/bin/env python3
"""
无人机模拟器

简单的单文件模拟器，模拟一架无人机的行为:
  1. 定期在控制台输出心跳信息（位置、电量、状态等）
  2. 启动一个 HTTP 服务，接收来自 brain_box 的导航指令
  3. 收到导航指令后，模拟飞行到目标位置并返回"已到达"

使用方式:
    python drone_simulator.py [--port 14580] [--brain-box http://localhost:9000]
"""
import argparse
import json
import random
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler


# ======================================================================
#  模拟无人机状态
# ======================================================================

class SimulatedDrone:
    """模拟无人机"""

    def __init__(self, drone_id: str):
        self.drone_id = drone_id
        self.position = {
            "latitude": 39.9042 + random.uniform(-0.001, 0.001),
            "longitude": 116.4074 + random.uniform(-0.001, 0.001),
            "altitude": 100.0,
        }
        self.battery = 100.0
        self.status = "online"
        self.armed = False
        self.navigating = False
        self._lock = threading.Lock()

    def heartbeat_info(self) -> dict:
        with self._lock:
            return {
                "drone_id": self.drone_id,
                "status": self.status,
                "position": dict(self.position),
                "battery": round(self.battery, 1),
                "armed": self.armed,
                "navigating": self.navigating,
                "timestamp": time.time(),
            }

    def navigate_to(self, target: dict) -> dict:
        """模拟飞行到目标位置"""
        with self._lock:
            self.navigating = True
            self.status = "busy"

        print(f"  [NAV] 收到导航指令 → 目标: lat={target.get('latitude')}, "
              f"lng={target.get('longitude')}, alt={target.get('altitude')}")
        print(f"  [NAV] 开始飞行...")

        # 模拟飞行过程
        steps = 3
        for i in range(1, steps + 1):
            time.sleep(1.0)
            with self._lock:
                for key in ("latitude", "longitude", "altitude"):
                    if key in target:
                        self.position[key] += (target[key] - self.position[key]) / (steps - i + 1)
                self.battery = max(0, self.battery - random.uniform(0.5, 1.5))
            print(f"  [NAV] 飞行中... ({i}/{steps})")

        with self._lock:
            self.position = {k: target.get(k, self.position.get(k, 0)) for k in self.position}
            self.navigating = False
            self.status = "online"

        print(f"  [NAV] ✓ 已到达目标位置")
        return {
            "status": "arrived",
            "drone_id": self.drone_id,
            "position": dict(self.position),
        }


# ======================================================================
#  HTTP 请求处理
# ======================================================================

# 全局引用，供 Handler 访问
_drone: SimulatedDrone | None = None


class DroneHandler(BaseHTTPRequestHandler):
    """处理来自 brain_box 的 HTTP 请求"""

    def log_message(self, format, *args):
        pass

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    def _send_json(self, data: dict, code: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ── 全部使用 POST ──

    def do_POST(self):
        assert _drone is not None
        data = self._read_json()

        if self.path == "/heartbeat":
            self._send_json(_drone.heartbeat_info())

        elif self.path == "/status":
            self._send_json({"status": "ok", "drone": _drone.heartbeat_info()})

        elif self.path == "/navigate":
            target = data.get("target_position", data)
            result = _drone.navigate_to(target)
            self._send_json(result)

        elif self.path == "/command":
            cmd_type = data.get("type", data.get("command", ""))
            print(f"  [CMD] 收到控制指令: {cmd_type} | {data}")
            self._send_json({"status": "ok", "command": cmd_type})

        else:
            self._send_json({"error": "not found"}, 404)


# ======================================================================
#  心跳上报（向 brain_box）
# ======================================================================

def heartbeat_loop(drone: SimulatedDrone, brain_box_url: str, interval: float):
    """定期向 brain_box 上报心跳（若不可达则仅打印到控制台）"""
    import urllib.request
    import urllib.error

    while True:
        info = drone.heartbeat_info()
        ts = time.strftime("%H:%M:%S")
        print(
            f"[{ts}] HEARTBEAT | id={info['drone_id']} "
            f"pos=({info['position']['latitude']:.4f}, "
            f"{info['position']['longitude']:.4f}, "
            f"{info['position']['altitude']:.1f}) "
            f"bat={info['battery']:.1f}% "
            f"status={info['status']}"
        )

        if brain_box_url:
            try:
                body = json.dumps(info).encode("utf-8")
                req = urllib.request.Request(
                    f"{brain_box_url}/api/v1/drones/command",
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=3)
            except Exception:
                pass

        # 模拟电量消耗
        with drone._lock:
            drone.battery = max(0, drone.battery - random.uniform(0.05, 0.15))

        time.sleep(interval)


# ======================================================================
#  Main
# ======================================================================

def main():
    global _drone

    parser = argparse.ArgumentParser(description="简单无人机模拟器")
    parser.add_argument("--drone-id", default="drone_sim_001", help="无人机 ID")
    parser.add_argument("--port", type=int, default=14580, help="HTTP 监听端口")
    parser.add_argument(
        "--brain-box",
        default="",
        help="BrainBox 地址（如 http://localhost:9000），为空则仅本地模拟",
    )
    parser.add_argument(
        "--heartbeat-interval",
        type=float,
        default=5.0,
        help="心跳上报间隔（秒）",
    )
    args = parser.parse_args()

    _drone = SimulatedDrone(args.drone_id)

    print("=" * 60)
    print(f"  无人机模拟器  drone_id = {args.drone_id}")
    print(f"  HTTP 监听端口: {args.port}")
    if args.brain_box:
        print(f"  BrainBox 地址: {args.brain_box}")
    else:
        print("  BrainBox 地址: 未设置（仅本地模拟）")
    print(f"  心跳间隔: {args.heartbeat_interval}s")
    print("=" * 60)
    print()

    # 启动心跳线程
    hb_thread = threading.Thread(
        target=heartbeat_loop,
        args=(_drone, args.brain_box, args.heartbeat_interval),
        daemon=True,
    )
    hb_thread.start()

    # 启动 HTTP 服务
    server = HTTPServer(("0.0.0.0", args.port), DroneHandler)
    print(f"HTTP 服务已启动: http://0.0.0.0:{args.port}")
    print("  POST /heartbeat  — 获取心跳信息")
    print("  POST /status     — 获取状态")
    print("  POST /navigate   — 接收导航指令 {'target_position': {'latitude':..., 'longitude':..., 'altitude':...}}")
    print("  POST /command    — 接收控制指令")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n模拟器已停止")
        server.shutdown()


if __name__ == "__main__":
    main()
