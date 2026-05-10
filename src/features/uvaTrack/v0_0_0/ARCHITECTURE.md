# 云边协同管控工具重构架构设计

## 目录结构
```
cloud_edge_manager_v2/
├── jivf.py                 # 入口文件，保持原有接口不变
├── config/
│   ├── __init__.py
│   └── settings.py         # 集中配置管理（存储路径、心跳超时等）
├── models/
│   ├── __init__.py
│   ├── base.py             # 基础模型
│   ├── device.py           # 设备模型
│   ├── server.py           # 服务器模型
│   └── task.py             # 任务及结果模型
├── storage/
│   ├── __init__.py
│   ├── local_storage.py    # 本地文件存储实现（历史任务、计算结果）
│   └── storage_manager.py  # 存储管理器接口
├── core/
│   ├── __init__.py
│   ├── manager.py          # 核心调度器
│   ├── heartbeat.py        # 心跳监控
│   ├── registry.py         # 流通道注册表
│   └── node_factory.py     # 节点工厂（用于自动识别和添加陌生节点）
└── utils/
    ├── __init__.py
    └── logger.py           # 日志工具
```

## 核心改进点设计

### 1. 陌生心跳自动识别与添加
在 `heartbeat` 接口中，当收到心跳时：
- 检查 `target_id` 是否在已注册列表中。
- 如果不在，且该节点未被标记为"已移除"（黑名单机制），则调用 `NodeFactory` 尝试自动注册。
- `NodeFactory` 根据心跳 payload 中的 `hardware_type` 或 `server_type` 自动推断节点类型并注册。
- **扩展性**：新增服务器/设备类型只需在 `NodeFactory` 注册新的类型处理器，无需修改心跳逻辑。

### 2. 移除后心跳忽略
- 在 `CloudEdgeManager` 中增加 `_removed_nodes` 集合（黑名单）。
- 调用 `remove_device` 或 `remove_server` 时，将 ID 加入黑名单。
- 收到心跳时，若 ID 在黑名单中，直接忽略，不进行自动注册。
- 只有通过 `add_device` 或 `add_server` 手动添加时，才从黑名单中移除。

### 3. 历史任务与计算结果存储
- 引入 `StorageManager`，支持将任务记录、计算结果、遥测数据持久化到磁盘。
- 存储路径通过 `config/settings.py` 配置，对外提供更改接口。
- 默认存储在 `data/tasks/` 和 `data/results/` 目录下。

### 4. 消息设计优化
心跳消息格式扩展，支持携带自动注册所需的元数据：
```json
{
    "target_type": "device", // 或 "server"
    "target_id": "robot_dog_nx_01",
    "location": {"lat": 30.27, "lng": 120.15, "alt": 5.0},
    "metadata": {
        "hardware_type": "jetson_xavier_nx", // 自动注册所需
        "supported_streams": ["video", "lidar_point_cloud"],
        "capacity": 10 // 服务器自动注册所需
    }
}
```
