#!/usr/bin/env python3
"""
无人机模拟器 — 通过 MAVLink 协议与类脑盒子通信

模拟一架无人机的行为:
  1. 通过 UDP 向类脑盒子发送 MAVLink HEARTBEAT 心跳消息
  2. 定期上报 GLOBAL_POSITION_INT 位置信息
  3. 监听类脑盒子下发的指令 (COMMAND_LONG / MISSION_ITEM_INT)
  4. 收到导航指令后模拟飞行，到达后在控制台输出"已到达"

使用方式:
    pip install pymavlink
    python drone_simulator.py [--target localhost:14550] [--system-id 1]

类脑盒子 config.yaml 中的 mavlink.connection_string 默认为 "udpin:0.0.0.0:14550"，
本模拟器通过 "udpout:<target>" 向其发送 MAVLink 数据包，brain_box 自动发现并注册设备。
"""
import argparse
import random
import sys
import threading
import time

try:
    from pymavlink import mavutil
except ImportError:
    print("错误: 需要安装 pymavlink")
    print("  pip install pymavlink")
    sys.exit(1)


class DroneSimulator:
    """模拟单架无人机，通过 MAVLink (UDP) 与类脑盒子通信"""

    def __init__(self, target: str, system_id: int):
        self.system_id = system_id
        self.device_id = f"drone_{system_id}"
        self.position = {
            "latitude": 39.9042 + random.uniform(-0.001, 0.001),
            "longitude": 116.4074 + random.uniform(-0.001, 0.001),
            "altitude": 100.0,
        }
        self.battery = 100.0
        self.armed = False
        self.navigating = False
        self._lock = threading.Lock()

        self.conn = mavutil.mavlink_connection(
            f"udpout:{target}",
            source_system=system_id,
            source_component=1,
        )

    # ------------------------------------------------------------------
    #  MAVLink 消息发送
    # ------------------------------------------------------------------

    def send_heartbeat(self) -> None:
        """发送 HEARTBEAT 心跳"""
        self.conn.mav.heartbeat_send(
            type=mavutil.mavlink.MAV_TYPE_QUADROTOR,
            autopilot=mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
            base_mode=(
                mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED
                | (mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED if self.armed else 0)
            ),
            custom_mode=0,
            system_status=mavutil.mavlink.MAV_STATE_ACTIVE,
        )

    def send_position(self) -> None:
        """发送 GLOBAL_POSITION_INT 位置信息"""
        with self._lock:
            lat = self.position["latitude"]
            lon = self.position["longitude"]
            alt = self.position["altitude"]

        self.conn.mav.global_position_int_send(
            time_boot_ms=int(time.time() * 1000) & 0xFFFFFFFF,
            lat=int(lat * 1e7),
            lon=int(lon * 1e7),
            alt=int(alt * 1000),
            relative_alt=int(alt * 1000),
            vx=0, vy=0, vz=0,
            hdg=0,
        )

    # ------------------------------------------------------------------
    #  心跳循环
    # ------------------------------------------------------------------

    def heartbeat_loop(self, interval: float = 1.0) -> None:
        """定期发送心跳和位置"""
        while True:
            self.send_heartbeat()
            self.send_position()

            with self._lock:
                lat = self.position["latitude"]
                lon = self.position["longitude"]
                alt = self.position["altitude"]
                bat = self.battery

            ts = time.strftime("%H:%M:%S")
            nav_flag = " [飞行中]" if self.navigating else ""
            print(
                f"[{ts}] HEARTBEAT | {self.device_id} "
                f"pos=({lat:.4f}, {lon:.4f}, {alt:.1f}) "
                f"bat={bat:.1f}% armed={self.armed}{nav_flag}"
            )

            with self._lock:
                self.battery = max(0, self.battery - random.uniform(0.05, 0.15))

            time.sleep(interval)

    # ------------------------------------------------------------------
    #  指令监听
    # ------------------------------------------------------------------

    def listen_loop(self) -> None:
        """监听类脑盒子下发的 MAVLink 指令"""
        while True:
            msg = self.conn.recv_match(blocking=True, timeout=1)
            if msg is None:
                continue

            msg_type = msg.get_type()

            if msg_type == "COMMAND_LONG":
                self._handle_command(msg)
            elif msg_type == "MISSION_COUNT":
                print(f"  [MISSION] 收到任务计数: {msg.count} 个航点")
            elif msg_type == "MISSION_ITEM_INT":
                self._handle_mission_item(msg)

    def _handle_command(self, msg) -> None:
        """处理 COMMAND_LONG 指令"""
        cmd_id = msg.command

        if cmd_id == mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM:
            arm = msg.param1 == 1
            self.armed = arm
            print(f"  [CMD] {'解锁 (Armed)' if arm else '上锁 (Disarmed)'}")

        elif cmd_id == mavutil.mavlink.MAV_CMD_NAV_TAKEOFF:
            alt = msg.param7
            print(f"  [CMD] 起飞到 {alt:.1f}m")
            with self._lock:
                self.position["altitude"] = alt

        elif cmd_id == mavutil.mavlink.MAV_CMD_NAV_LAND:
            print("  [CMD] 降落")
            with self._lock:
                self.position["altitude"] = 0.0

        elif cmd_id == mavutil.mavlink.MAV_CMD_NAV_WAYPOINT:
            lat = msg.param5 / 1e7 if abs(msg.param5) > 1000 else msg.param5
            lon = msg.param6 / 1e7 if abs(msg.param6) > 1000 else msg.param6
            alt = msg.param7
            print(f"  [NAV] 收到航点指令 → lat={lat:.6f}, lon={lon:.6f}, alt={alt:.1f}")
            threading.Thread(
                target=self._navigate_to,
                args=(lat, lon, alt),
                daemon=True,
            ).start()

        else:
            print(f"  [CMD] 未知指令: command_id={cmd_id}")

    def _handle_mission_item(self, msg) -> None:
        """处理 MISSION_ITEM_INT 航点"""
        lat = msg.x / 1e7
        lon = msg.y / 1e7
        alt = msg.z
        seq = msg.seq
        print(f"  [MISSION] 航点 #{seq}: lat={lat:.6f}, lon={lon:.6f}, alt={alt:.1f}")
        threading.Thread(
            target=self._navigate_to,
            args=(lat, lon, alt),
            daemon=True,
        ).start()

    # ------------------------------------------------------------------
    #  模拟飞行
    # ------------------------------------------------------------------

    def _navigate_to(self, lat: float, lon: float, alt: float) -> None:
        """模拟飞行到目标位置"""
        target = {"latitude": lat, "longitude": lon, "altitude": alt}
        self.navigating = True

        print(f"  [NAV] 开始飞行 → ({lat:.6f}, {lon:.6f}, {alt:.1f})")

        steps = 3
        for i in range(1, steps + 1):
            time.sleep(1.0)
            with self._lock:
                for key in ("latitude", "longitude", "altitude"):
                    diff = target[key] - self.position[key]
                    self.position[key] += diff / (steps - i + 1)
                self.battery = max(0, self.battery - random.uniform(0.5, 1.5))
            print(f"  [NAV] 飞行中... ({i}/{steps})")

        with self._lock:
            self.position = dict(target)
        self.navigating = False

        print(f"  [NAV] 已到达目标位置 ({lat:.6f}, {lon:.6f}, {alt:.1f})")


# ======================================================================
#  Main
# ======================================================================

def main():
    parser = argparse.ArgumentParser(
        description="无人机模拟器 — MAVLink 协议与类脑盒子通信"
    )
    parser.add_argument(
        "--target",
        default="localhost:14550",
        help="类脑盒子 MAVLink 地址 (host:port)，默认 localhost:14550",
    )
    parser.add_argument(
        "--system-id",
        type=int,
        default=1,
        help="MAVLink System ID，默认 1（brain_box 中显示为 drone_<id>）",
    )
    parser.add_argument(
        "--heartbeat-interval",
        type=float,
        default=1.0,
        help="心跳发送间隔（秒），默认 1.0",
    )
    args = parser.parse_args()

    drone = DroneSimulator(args.target, args.system_id)

    print("=" * 60)
    print("  无人机模拟器 (MAVLink UDP)")
    print(f"  System ID : {args.system_id}")
    print(f"  Device ID : drone_{args.system_id}")
    print(f"  目标地址  : udpout:{args.target}")
    print(f"  心跳间隔  : {args.heartbeat_interval}s")
    print("=" * 60)
    print()

    # 心跳线程
    hb = threading.Thread(
        target=drone.heartbeat_loop,
        args=(args.heartbeat_interval,),
        daemon=True,
    )
    hb.start()

    # 主线程监听指令
    print("正在监听类脑盒子指令...\n")
    try:
        drone.listen_loop()
    except KeyboardInterrupt:
        print("\n模拟器已停止")


if __name__ == "__main__":
    main()
