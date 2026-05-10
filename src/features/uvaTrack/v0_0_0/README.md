## CloudEdgeManager — 云边协同管控工具 v2.0.0

### 加载配置

```json
{
    "dtype": "uvaTrack",
    "dir_name": "uvaTrack",
    "version": "2.0.0",
    "file_name": "jivf",
    "class_name": "CTest",
    "heartbeat_config": {
        "check_interval_s": 5.0,
        "device_timeout_s": 15.0,
        "server_timeout_s": 30.0
    },
    "storage_config": {
        "tasks_dir": "./data/tasks",
        "results_dir": "./data/results",
        "telemetry_dir": "./data/telemetry",
        "logs_dir": "./data/logs"
    },
    "auto_register_config": {
        "enabled": true,
        "timeout_s": 60.0
    }
}
```

### 模块结构

```
cloud_edge_manager_v2/
├── jivf.py                 # 工具入口类 CTest，平台通过 subfunc 分发调用
├── config/
│   ├── __init__.py
│   └── settings.py         # 集中配置管理（存储路径、心跳超时等）
├── models/
│   ├── __init__.py
│   ├── base.py             # 基础模型和枚举
│   ├── device.py           # 设备模型
│   ├── server.py           # 服务器模型
│   └── task.py             # 任务、流通道、结果和遥测模型
├── storage/
│   ├── __init__.py
│   ├── storage_manager.py  # 存储管理器抽象接口
│   └── local_storage.py    # 本地文件存储实现
├── core/
│   ├── __init__.py
│   ├── manager.py          # 核心调度器（单例）
│   ├── heartbeat.py        # 心跳监控守护线程
│   ├── registry.py         # 流通道注册表
│   └── node_factory.py     # 节点工厂（自动识别和创建节点）
├── utils/
│   ├── __init__.py
│   └── logger.py           # 日志工具
├── ARCHITECTURE.md         # 架构设计文档
└── README.md
```

### 核心功能

| subfunc              | 说明                                             |
|----------------------|--------------------------------------------------|
| add_server           | 注册计算服务器节点到云端调度池                   |
| remove_server        | 从调度池中安全移除指定服务器                     |
| list_servers         | 获取可用的计算服务器列表及当前负载状态           |
| add_device           | 注册边缘设备到管控系统                           |
| remove_device        | 从系统中注销边缘设备                             |
| list_devices         | 获取已注册的边缘设备列表及在线状态               |
| assign_and_start_task| 指定设备连接服务器执行计算任务                   |
| stop_task            | 中断指定设备与服务器之间的任务和数据流           |

### 扩展接口

| subfunc              | 说明                                             |
|----------------------|--------------------------------------------------|
| heartbeat            | 设备/服务器心跳上报（支持自动识别和添加）       |
| get_device_info      | 获取设备详细信息（含流通道、遥测和当前任务）     |
| get_task_info        | 查询任务详情（含计算结果列表）                   |
| update_location      | 设备位置上报                                     |

### 通用数据交互接口

| subfunc                  | 说明                                                                 |
|--------------------------|----------------------------------------------------------------------|
| submit_task_result       | 服务器提交任务计算结果（通用，result_type 标识类型，payload 为数据） |
| update_device_telemetry  | 设备/服务器上报遥测数据（通用，telemetry_type 标识类型，data 为数据）|

### 核心改进点

#### 1. 陌生心跳自动识别与添加

在 `heartbeat` 接口中，当收到心跳时：

- 检查 `target_id` 是否在已注册列表中
- 如果不在，且该节点未被标记为"已移除"（黑名单机制），则调用 `NodeFactory` 尝试自动注册
- `NodeFactory` 根据心跳 payload 中的 `hardware_type` 或 `server_type` 自动推断节点类型并注册
- **扩展性**：新增服务器/设备类型只需在 `NodeFactory` 注册新的类型处理器，无需修改心跳逻辑

**心跳消息格式（支持自动注册）**：

```json
{
    "target_type": "device",
    "target_id": "robot_dog_nx_01",
    "location": {"lat": 30.27, "lng": 120.15, "alt": 5.0},
    "metadata": {
        "hardware_type": "jetson_xavier_nx",
        "supported_streams": ["video", "lidar_point_cloud"]
    }
}
```

#### 2. 移除后心跳忽略

- 在 `CloudEdgeManager` 中增加 `_removed_nodes` 集合（黑名单）
- 调用 `remove_device` 或 `remove_server` 时，将 ID 加入黑名单
- 收到心跳时，若 ID 在黑名单中，直接忽略，不进行自动注册
- 只有通过 `add_device` 或 `add_server` 手动添加时，才从黑名单中移除

#### 3. 历史任务与计算结果存储

- 引入 `StorageManager` 抽象接口和 `LocalStorage` 实现
- 支持将任务记录、计算结果、遥测数据持久化到磁盘
- 存储路径通过 `config/settings.py` 配置，对外提供更改接口
- 默认存储在 `data/tasks/`、`data/results/`、`data/telemetry/` 目录下

**配置存储路径**：

```python
from config.settings import settings

# 方式 1：设置基础目录
settings.set_base_dir("/path/to/data")

# 方式 2：分别设置各目录
settings.set_storage_paths(
    tasks_dir="/path/to/tasks",
    results_dir="/path/to/results",
    telemetry_dir="/path/to/telemetry",
    logs_dir="/path/to/logs"
)
```

#### 4. 服务器/设备节点易于扩展

**添加新的设备类型**：

```python
from core.node_factory import NodeFactory

def create_custom_device(device_id, metadata):
    from models import EdgeDevice
    return EdgeDevice(
        device_id=device_id,
        hardware_type=metadata.get("hardware_type", "custom"),
        supported_streams=set(metadata.get("supported_streams", [])),
        metadata=metadata
    )

# 在 NodeFactory 中注册
factory = NodeFactory()
factory.register_device_handler("custom_type", create_custom_device)
```

**添加新的服务器类型**：

```python
def create_custom_server(server_id, ip_address, metadata):
    from models import ServerNode
    return ServerNode(
        server_id=server_id,
        ip_address=ip_address,
        capacity=metadata.get("capacity", 10),
        tags=metadata.get("tags", []),
        metadata=metadata
    )

factory.register_server_handler("custom_server", create_custom_server)
```

### 设计特性

1. **心跳机制 (Heartbeat)**: 守护线程定期检测设备/服务器活跃状态，超时自动标记离线并释放资源
2. **数据流隔离**: 信令通道(WebSocket)与媒体通道(WebRTC/UDP)在端口和协议层面逻辑隔离
3. **模拟设备模式**: `is_simulated=true` 注册虚拟设备用于纯代码测试，跳过心跳检测
4. **任务抢占与恢复**: 重复分配时自动抢占旧任务，平滑释放服务器资源
5. **灵活扩展**: `custom_payloads` 字段支持任意自定义配置透传
6. **低耦合设计**: 通用数据交互接口（submit_task_result / update_device_telemetry）与具体设备类型无关，通过 result_type / telemetry_type 标识数据类型，payload / data 由调用方自定义格式
7. **自动识别与添加**: 陌生心跳自动识别设备/服务器类型并添加到系统
8. **黑名单机制**: 移除后的节点进入黑名单，后续心跳直接忽略，只有手动添加才能重新启用
9. **持久化存储**: 任务、结果、遥测数据自动保存到本地文件系统，支持路径配置
10. **分层架构**: 清晰的模块划分，易于维护和扩展

### 使用示例

#### 基础配置

```python
from config.settings import settings

# 配置存储路径
settings.set_storage_paths(
    tasks_dir="./data/tasks",
    results_dir="./data/results",
    telemetry_dir="./data/telemetry"
)

# 配置心跳参数
settings.set_heartbeat_config(
    check_interval_s=5.0,
    device_timeout_s=15.0,
    server_timeout_s=30.0
)

# 启用自动注册
settings.set_auto_register(enabled=True, timeout_s=60.0)
```

#### 初始化管理器

```python
from core.manager import CloudEdgeManager

manager = CloudEdgeManager(
    heartbeat_interval=5.0,
    device_timeout=15.0,
    server_timeout=30.0
)
```

#### 添加服务器和设备

```python
# 添加服务器
manager.add_server(
    server_id="svr_01",
    ip_address="192.168.1.100",
    capacity=10,
    tags=["gpu", "path_planning"]
)

# 添加设备
manager.add_device(
    device_id="robot_01",
    hardware_type="jetson_xavier_nx",
    supported_streams=["video", "lidar_point_cloud"]
)
```

#### 分配任务

```python
manager.assign_and_start_task(
    device_id="robot_01",
    server_id="svr_01",
    task_config={
        "algorithm": "a_star",
        "frequency_hz": 10,
        "enable_video_stream": True,
        "custom_payloads": {...}
    }
)
```

#### 心跳上报（支持自动注册）

```python
# 设备心跳（如果设备不存在且未被移除，则自动注册）
manager.refresh_device_heartbeat(
    device_id="robot_02",
    location={"lat": 30.27, "lng": 120.15},
    heartbeat_data={
        "metadata": {
            "hardware_type": "jetson_xavier_nx",
            "supported_streams": ["video"]
        }
    }
)

# 服务器心跳
manager.refresh_server_heartbeat(server_id="svr_01")
```

#### 提交结果和遥测

```python
# 提交任务结果
manager.submit_task_result(
    task_id="task_xxx",
    result_type="trajectory",
    payload={"waypoints": [...]}
)

# 上报遥测数据
manager.update_device_telemetry(
    device_id="robot_01",
    telemetry_type="position",
    data={"position": {"lat": 30.27, "lng": 120.15}}
)
```

### 扩展 NodeFactory

要支持新的设备或服务器类型，只需在 `NodeFactory` 中注册对应的处理器：

```python
from core.node_factory import NodeFactory

factory = NodeFactory()

# 注册自定义设备处理器
factory.register_device_handler("my_device_type", my_device_creator)

# 注册自定义服务器处理器
factory.register_server_handler("my_server_type", my_server_creator)
```

新增的类型会自动在心跳处理时被识别和使用，无需修改心跳逻辑。

### 版本变更

**v2.0.0 相比 v0.0.0 的改进**：

- ✅ 分层目录结构，模块清晰
- ✅ 集中配置管理（settings.py）
- ✅ 陌生心跳自动识别与添加
- ✅ 黑名单机制（移除后心跳忽略）
- ✅ 持久化存储支持（任务、结果、遥测）
- ✅ 存储路径可配置接口
- ✅ NodeFactory 易于扩展新设备/服务器类型
- ✅ 完整的日志系统
- ✅ 更好的代码组织和文档
