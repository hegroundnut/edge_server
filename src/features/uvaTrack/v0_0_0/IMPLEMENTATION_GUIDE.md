# 实现指南

## 快速开始

### 1. 项目结构概览

```
cloud_edge_manager_v2/
├── jivf.py                      # 入口文件（保持原有接口）
├── config/                      # 配置管理
│   ├── __init__.py
│   └── settings.py              # 全局配置（单例）
├── models/                      # 数据模型
│   ├── __init__.py
│   ├── base.py                  # 枚举和基础类型
│   ├── device.py                # EdgeDevice 模型
│   ├── server.py                # ServerNode 模型
│   └── task.py                  # 任务相关模型
├── storage/                     # 存储管理
│   ├── __init__.py
│   ├── storage_manager.py       # 抽象接口
│   └── local_storage.py         # 本地文件实现
├── core/                        # 核心模块
│   ├── __init__.py
│   ├── manager.py               # CloudEdgeManager（单例）
│   ├── heartbeat.py             # 心跳监控
│   ├── registry.py              # 流通道注册表
│   └── node_factory.py          # 节点工厂
├── utils/                       # 工具模块
│   ├── __init__.py
│   └── logger.py                # 日志配置
├── ARCHITECTURE.md              # 架构设计文档
├── IMPLEMENTATION_GUIDE.md      # 本文件
└── README.md                    # 使用文档
```

### 2. 核心改进点详解

#### 2.1 陌生心跳自动识别与添加

**原理**：

当收到心跳时，系统会：

1. 检查节点 ID 是否已注册
2. 如果未注册且不在黑名单中，调用 `NodeFactory` 自动创建节点
3. `NodeFactory` 根据心跳数据中的 `hardware_type` 或 `server_type` 选择对应的处理器
4. 新节点自动添加到系统

**关键代码**：

```python
# core/manager.py - refresh_device_heartbeat 方法
def refresh_device_heartbeat(self, device_id, location=None, heartbeat_data=None):
    # 检查黑名单
    if device_id in self._removed_nodes:
        return False
    
    # 设备已存在
    if device_id in self._devices:
        # 更新心跳
        device = self._devices[device_id]
        device.last_active_time = time.time()
        return True
    
    # 自动注册
    if not settings.auto_register_enabled or heartbeat_data is None:
        return False
    
    device = self._node_factory.create_device_from_heartbeat(device_id, heartbeat_data)
    if device:
        self._devices[device_id] = device
        return True
    
    return False
```

**扩展性**：

新增设备类型无需修改心跳逻辑，只需在 `NodeFactory` 中注册处理器：

```python
# 注册新的设备类型处理器
factory.register_device_handler("my_device", create_my_device)

# 心跳时自动使用该处理器
```

#### 2.2 移除后心跳忽略（黑名单机制）

**原理**：

- 移除设备/服务器时，将其 ID 加入 `_removed_nodes` 黑名单
- 收到心跳时，先检查黑名单，如果在黑名单中直接忽略
- 只有通过 `add_device` 或 `add_server` 手动添加时，才从黑名单中移除

**关键代码**：

```python
# core/manager.py - remove_device 方法
def remove_device(self, device_id):
    # ... 清理任务和流通道 ...
    self._removed_nodes.add(device_id)  # 加入黑名单
    return result

# core/manager.py - add_device 方法
def add_device(self, device_id, ...):
    # ... 创建设备 ...
    self._removed_nodes.discard(device_id)  # 从黑名单移除
    return result

# core/manager.py - refresh_device_heartbeat 方法
def refresh_device_heartbeat(self, device_id, ...):
    if device_id in self._removed_nodes:  # 检查黑名单
        return False
    # ... 继续处理 ...
```

#### 2.3 历史任务与计算结果存储

**原理**：

- `StorageManager` 定义存储接口
- `LocalStorage` 实现本地文件存储
- 任务、结果、遥测数据自动保存为 JSON 文件
- 存储路径通过 `Settings` 配置

**目录结构**：

```
data/
├── tasks/
│   ├── task_abc123.json
│   ├── task_def456.json
│   └── ...
├── results/
│   ├── res_abc123.json
│   ├── res_def456.json
│   └── ...
├── telemetry/
│   ├── device_01/
│   │   ├── telemetry_000000.json
│   │   ├── telemetry_000001.json
│   │   └── ...
│   ├── device_02/
│   │   └── ...
│   └── ...
└── logs/
    └── uvaTrack.log
```

**配置存储路径**：

```python
from config.settings import settings

# 方式 1：设置基础目录
settings.set_base_dir("/custom/path")

# 方式 2：分别设置各目录
settings.set_storage_paths(
    tasks_dir="/path/to/tasks",
    results_dir="/path/to/results",
    telemetry_dir="/path/to/telemetry",
    logs_dir="/path/to/logs"
)
```

**关键代码**：

```python
# core/manager.py - assign_and_start_task 方法
task = TaskRecord(...)
self._tasks[task.task_id] = task
self._storage.save_task(task.task_id, task.to_dict())  # 持久化

# core/manager.py - submit_task_result 方法
result = TaskResult(...)
self._task_results.setdefault(task_id, []).append(result)
self._storage.save_result(result.result_id, result.to_dict())  # 持久化

# core/manager.py - update_device_telemetry 方法
telemetry = DeviceTelemetry(...)
self._device_telemetry[device_id] = telemetry
self._storage.save_telemetry(device_id, telemetry.to_dict())  # 持久化
```

#### 2.4 服务器/设备节点易于扩展

**原理**：

`NodeFactory` 维护类型处理器映射表，通过注册新的处理器来支持新的节点类型。

**添加新的设备类型**：

```python
from core.node_factory import NodeFactory
from models import EdgeDevice

def create_custom_device(device_id, metadata):
    """创建自定义设备"""
    return EdgeDevice(
        device_id=device_id,
        hardware_type=metadata.get("hardware_type", "custom"),
        is_simulated=metadata.get("is_simulated", False),
        supported_streams=set(metadata.get("supported_streams", [])),
        group_id=metadata.get("group_id", "custom"),
        metadata=metadata
    )

# 获取 NodeFactory 实例并注册
factory = NodeFactory()
factory.register_device_handler("custom_device", create_custom_device)
```

**添加新的服务器类型**：

```python
from models import ServerNode

def create_custom_server(server_id, ip_address, metadata):
    """创建自定义服务器"""
    return ServerNode(
        server_id=server_id,
        ip_address=ip_address,
        capacity=metadata.get("capacity", 10),
        tags=metadata.get("tags", []),
        metadata=metadata
    )

factory.register_server_handler("custom_server", create_custom_server)
```

**使用自定义类型**：

心跳消息中指定 `hardware_type` 或 `server_type`，系统会自动使用对应的处理器：

```json
{
    "target_type": "device",
    "target_id": "my_device_01",
    "metadata": {
        "hardware_type": "custom_device"
    }
}
```

### 3. 配置管理

#### 3.1 Settings 单例

`Settings` 是全局配置管理器，采用单例模式：

```python
from config.settings import settings

# 获取配置
print(settings.tasks_dir)
print(settings.device_timeout_s)

# 修改配置
settings.set_storage_paths(tasks_dir="/new/path")
settings.set_heartbeat_config(device_timeout_s=20.0)
```

#### 3.2 配置项

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `base_dir` | 基础目录 | `.` |
| `tasks_dir` | 任务存储目录 | `./data/tasks` |
| `results_dir` | 结果存储目录 | `./data/results` |
| `telemetry_dir` | 遥测存储目录 | `./data/telemetry` |
| `logs_dir` | 日志目录 | `./data/logs` |
| `heartbeat_check_interval_s` | 心跳检查间隔 | `5.0` |
| `device_timeout_s` | 设备超时 | `15.0` |
| `server_timeout_s` | 服务器超时 | `30.0` |
| `auto_register_enabled` | 是否启用自动注册 | `True` |
| `auto_register_timeout_s` | 自动注册超时 | `60.0` |

### 4. 消息设计

#### 4.1 心跳消息格式

**设备心跳（支持自动注册）**：

```json
{
    "target_type": "device",
    "target_id": "robot_dog_nx_01",
    "location": {
        "lat": 30.27,
        "lng": 120.15,
        "alt": 5.0
    },
    "metadata": {
        "hardware_type": "jetson_xavier_nx",
        "supported_streams": ["video", "lidar_point_cloud"],
        "group_id": "jetson",
        "is_simulated": false
    }
}
```

**服务器心跳**：

```json
{
    "target_type": "server",
    "target_id": "svr_node_01"
}
```

#### 4.2 消息设计原则

1. **通用性**：`target_type` 和 `target_id` 是通用字段，支持扩展
2. **元数据灵活**：`metadata` 字段包含自动注册所需的信息
3. **向后兼容**：已注册节点的心跳无需 `metadata` 字段
4. **可扩展**：新增节点类型只需在 `metadata` 中添加相应字段

### 5. 扩展示例

#### 5.1 添加新的存储后端

```python
from storage.storage_manager import StorageManager
from typing import Dict, Any, List, Optional

class DatabaseStorage(StorageManager):
    """数据库存储实现"""
    
    def __init__(self, db_url):
        self.db_url = db_url
        # 初始化数据库连接
    
    def save_task(self, task_id: str, task_data: Dict[str, Any]) -> bool:
        # 实现数据库保存逻辑
        pass
    
    def load_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        # 实现数据库加载逻辑
        pass
    
    # ... 实现其他方法 ...
```

#### 5.2 添加新的设备类型

```python
# 定义处理器
def create_drone_device(device_id, metadata):
    from models import EdgeDevice
    return EdgeDevice(
        device_id=device_id,
        hardware_type="drone",
        supported_streams=set(["video", "thermal", "lidar"]),
        group_id="drones",
        metadata=metadata
    )

# 注册处理器
from core.node_factory import NodeFactory
factory = NodeFactory()
factory.register_device_handler("drone", create_drone_device)

# 使用心跳自动注册
heartbeat = {
    "target_type": "device",
    "target_id": "drone_01",
    "metadata": {
        "hardware_type": "drone"
    }
}
manager.refresh_device_heartbeat("drone_01", heartbeat_data=heartbeat)
```

### 6. 常见问题

**Q: 如何禁用自动注册？**

A: 在配置中禁用：

```python
settings.set_auto_register(enabled=False)
```

**Q: 如何自定义存储路径？**

A: 使用 Settings 配置：

```python
settings.set_storage_paths(
    tasks_dir="/custom/tasks",
    results_dir="/custom/results"
)
```

**Q: 如何添加新的设备类型？**

A: 在 NodeFactory 中注册处理器，无需修改其他代码。

**Q: 移除的设备能否重新添加？**

A: 可以，调用 `add_device` 会自动从黑名单中移除。

**Q: 心跳超时后会发生什么？**

A: 设备/服务器会被标记为离线，运行中的任务会被停止。

### 7. 性能优化建议

1. **批量操作**：对于大量设备，考虑批量导入而不是逐个添加
2. **存储优化**：对于高频遥测数据，考虑使用数据库存储而不是文件
3. **心跳间隔**：根据实际需求调整心跳检查间隔
4. **日志级别**：生产环境建议使用 WARNING 级别以减少日志开销

### 8. 测试建议

```python
# 单元测试示例
def test_auto_register_device():
    manager = CloudEdgeManager()
    
    # 发送陌生设备心跳
    result = manager.refresh_device_heartbeat(
        device_id="test_device",
        heartbeat_data={
            "metadata": {
                "hardware_type": "jetson_xavier_nx"
            }
        }
    )
    
    assert result is True
    assert "test_device" in manager._devices

def test_blacklist_mechanism():
    manager = CloudEdgeManager()
    
    # 添加设备
    manager.add_device("device_01", "jetson_xavier_nx")
    
    # 移除设备
    manager.remove_device("device_01")
    
    # 尝试通过心跳重新添加（应该失败）
    result = manager.refresh_device_heartbeat(
        device_id="device_01",
        heartbeat_data={"metadata": {"hardware_type": "jetson_xavier_nx"}}
    )
    
    assert result is False
    
    # 手动添加（应该成功）
    result = manager.add_device("device_01", "jetson_xavier_nx")
    assert result["code"] == 0
```

