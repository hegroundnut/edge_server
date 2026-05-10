# 从 v0.0.0 迁移到 v2.0.0

## 概述

v2.0.0 是 v0.0.0 的重构版本，保持了所有 `jivf.py` 的公开接口不变，但内部进行了重大改进。

## 主要改进

| 功能 | v0.0.0 | v2.0.0 | 说明 |
|------|--------|--------|------|
| 目录结构 | 平铺 | 分层 | 代码更清晰，易于维护 |
| 陌生心跳 | 直接忽略 | 自动识别添加 | 支持自动发现新设备/服务器 |
| 移除后心跳 | 直接忽略 | 黑名单机制 | 更明确的状态管理 |
| 存储路径 | 硬编码 | 可配置 | 灵活的存储位置 |
| 节点扩展 | 修改代码 | 注册处理器 | 无需修改核心代码 |
| 持久化 | 内存存储 | 文件/数据库 | 支持数据恢复 |
| 日志系统 | 基础 | 完整 | 更好的调试支持 |

## 迁移步骤

### 1. 替换文件

将原有的单文件结构替换为新的分层结构：

```bash
# 备份原有代码
cp -r old_version backup/

# 使用新版本
cp -r cloud_edge_manager_v2/* target_location/
```

### 2. 更新配置

原有配置方式：

```json
{
    "heartbeat_config": {
        "check_interval_s": 5.0,
        "device_timeout_s": 15.0,
        "server_timeout_s": 30.0
    }
}
```

新的配置方式（兼容原有配置，并支持扩展）：

```json
{
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

### 3. 代码兼容性

所有公开接口保持不变，现有代码无需修改：

```python
# v0.0.0 的代码仍然可以工作
manager.add_device("device_01", "jetson_xavier_nx")
manager.add_server("server_01", "192.168.1.100")
manager.assign_and_start_task("device_01", "server_01", task_config)
```

### 4. 新功能使用

#### 4.1 自动注册

在心跳消息中包含 `metadata` 字段，系统会自动识别和添加新设备：

```python
# 新增功能：自动注册
heartbeat_data = {
    "target_type": "device",
    "target_id": "new_device",
    "metadata": {
        "hardware_type": "jetson_xavier_nx",
        "supported_streams": ["video"]
    }
}
manager.refresh_device_heartbeat("new_device", heartbeat_data=heartbeat_data)
```

#### 4.2 配置存储路径

```python
from config.settings import settings

settings.set_storage_paths(
    tasks_dir="/custom/tasks",
    results_dir="/custom/results"
)
```

#### 4.3 扩展节点类型

```python
from core.node_factory import NodeFactory

def create_custom_device(device_id, metadata):
    from models import EdgeDevice
    return EdgeDevice(
        device_id=device_id,
        hardware_type=metadata.get("hardware_type"),
        metadata=metadata
    )

factory = NodeFactory()
factory.register_device_handler("custom", create_custom_device)
```

## 行为变化

### 心跳处理

| 场景 | v0.0.0 | v2.0.0 |
|------|--------|--------|
| 已注册设备心跳 | 更新状态 | 更新状态 ✓ |
| 陌生设备心跳 | 忽略 | 自动注册（可配置） ✓ |
| 已移除设备心跳 | 忽略 | 忽略（黑名单） ✓ |
| 重新添加已移除设备 | 不支持 | 支持 ✓ |

### 存储

| 操作 | v0.0.0 | v2.0.0 |
|------|--------|--------|
| 保存任务 | 内存 | 文件 + 内存 ✓ |
| 保存结果 | 内存 | 文件 + 内存 ✓ |
| 保存遥测 | 内存 | 文件 + 内存 ✓ |
| 自定义路径 | 不支持 | 支持 ✓ |

## 常见问题

**Q: 现有代码需要修改吗？**

A: 不需要。所有公开接口保持不变，现有代码可以直接使用。

**Q: 如何禁用自动注册？**

A: 在配置中设置 `auto_register_config.enabled: false`。

**Q: 数据会丢失吗？**

A: 不会。v2.0.0 新增了持久化存储，但内存中的数据结构保持不变。

**Q: 如何迁移现有数据？**

A: v2.0.0 支持从内存中导出数据到文件，可以编写迁移脚本。

**Q: 性能会有影响吗？**

A: 性能基本相同。新增的文件 I/O 操作可以通过配置调整（如禁用持久化）来优化。

## 回滚方案

如果需要回滚到 v0.0.0：

1. 备份 v2.0.0 的数据（`data/` 目录）
2. 恢复原有的代码文件
3. 如需恢复数据，可以编写脚本从 JSON 文件重新加载

## 支持

如有问题，请参考：

- `README.md` - 完整功能文档
- `ARCHITECTURE.md` - 架构设计
- `IMPLEMENTATION_GUIDE.md` - 实现细节
