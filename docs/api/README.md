# DaHua_CGI API Documentation

> 大华 CGI 设备批量配置工具 — 模块接口文档

## 项目概述

本项目用于通过 CGI 协议对大华摄像头/NVR 设备进行批量配置。支持 Excel 导入设备列表、Ping 在线检测、批量执行 CGI 命令、结果导出。

## 目录结构

```
src/
├── main.py                       # 入口（GUI/TUI）
├── ui/                           # 界面层
├── utils/                        # 核心工具模块
│   ├── __init__.py
│   ├── async_executor.py         # 异步 CGI 请求执行器
│   ├── config_manager.py         # 配置管理（双源加载）
│   ├── cgi_reference_manager.py  # CGI 参数引用库
│   ├── device_manager.py         # 设备管理（加载/检测/配置执行）
│   └── log_manager.py            # 日志管理（文件、轮转、CGI 元数据）
└── config/                       # 配置文件目录
```

## 模块索引

| 模块 | 文件 | 核心类 | 职责 |
|------|------|--------|------|
| 异步执行器 | `async_executor.py` | `SyncRequestsExecutor`, `AsyncExecutor`, `AsyncIOManager` | CGI 请求发送（同步 + 异步线程池） |
| 配置管理 | `config_manager.py` | `ConfigManager` | 配置加载（YAML 优先、环境变量覆盖、旧 JSON 兼容） |
| CGI 参数引用 | `cgi_reference_manager.py` | `CGIReferenceManager` | 参数库维护、模块分类、参考数据 |
| 设备管理 | `device_manager.py` | `DeviceLoader`, `DeviceDetector`, `ConfigExecutor` | 设备 Excel 导入、Ping 检测、批量 CGI 配置执行 |
| 日志管理 | `log_manager.py` | `LogManager` | 日志记录、文件轮转、CGI 元数据记录、Excel 导出 |

## 模块间依赖关系

```
main.py / ui/
    ├── device_manager.py ────────────────► async_executor.py
    │       │                                   │
    │       └──► log_manager.py                  │
    │                                            │
    └── config_manager.py ─────────────────► async_executor.py
    │       │
    │       └──► cgi_reference_manager.py
    │
    └── log_manager.py
```

## 快速开始

```python
# 1. 加载配置
from utils.config_manager import ConfigManager
config = ConfigManager.load_config()

# 2. 初始化日志
from utils.log_manager import LogManager
log_manager = LogManager(log_level="INFO")

# 3. 加载设备
from utils.device_manager import DeviceLoader
loader = DeviceLoader(log_manager)
devices, count = loader.load_from_excel("设备列表.xlsx")

# 4. 检测在线
from utils.device_manager import DeviceDetector
detector = DeviceDetector(config, log_manager)
online, offline = detector.detect_devices(devices)

# 5. 执行配置
from utils.device_manager import ConfigExecutor
executor = ConfigExecutor(config, log_manager, use_async=True)
results = executor.execute_batch(devices, mode="standard")

# 6. 查看结果
for r in results:
    print(f"{r['ip']}: 成功 {r['success_commands']}/{r['total_commands']}")
```

## 详细接口

- [async_executor.py](async_executor.md) — CGI 请求发送与认证
- [config_manager.py](config_manager.md) — 配置加载与管理
- [cgi_reference_manager.py](cgi_reference_manager.md) — 参数引用库
- [device_manager.py](device_manager.md) — 设备导入/检测/配置执行
- [log_manager.py](log_manager.md) — 日志与结果导出
