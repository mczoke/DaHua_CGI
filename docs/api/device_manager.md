# device_manager.py — 设备管理模块

## 模块概述

设备管理的核心模块，提供三个主要功能：

1. **设备加载** (`DeviceLoader`) — 从 Excel 导入设备列表
2. **设备检测** (`DeviceDetector`) — Ping 扫描在线设备
3. **配置执行** (`ConfigExecutor`) — 批量 CGI 配置执行（同步 + 异步双模式）

**版本:** 9.5

## 数据类: DeviceInfo

```python
@dataclass
class DeviceInfo:
    index: int              # 设备在列表中的索引
    ip: str                 # IP 地址
    port: str = "80"        # HTTP 端口
    username: str = "admin" # 用户名
    password: str = ""      # 密码
    status: str = "未检测"  # 当前状态
    online: bool = False    # 是否在线
    selected: bool = True   # 是否选中
    variables: Dict[str, str] = field(default_factory=dict)  # 自定义变量
    result: Optional[Dict] = None  # 配置结果
    excel_row: int = 0      # Excel 中的行号
    last_message: str = ""  # 最后状态信息
```

**方法:**

| 方法 | 返回 | 说明 |
|------|------|------|
| `get_display_info()` | `str` | 获取显示名称（设备名称 + IP:端口） |

---

## 类: DeviceLoader

从 Excel 文件加载设备列表。

### 构造函数

```python
DeviceLoader(log_manager)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `log_manager` | `LogManager` | 日志管理器实例 |

### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `devices` | `List[DeviceInfo]` | 已加载的设备列表 |
| `excel_source_file` | `str` | Excel 源文件路径 |
| `loaded_time` | `datetime` | 加载时间戳 |

### 方法

#### `load_from_excel(file_path, mode="standard") -> Tuple[List[DeviceInfo], int]`

从 Excel 文件加载设备。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `file_path` | `str` | — | Excel 文件路径 |
| `mode` | `str` | `"standard"` | 加载模式，`"customized"` 模式会提取变量列 |

**返回:** `(devices列表, 有效设备数)`

**Excel 列自动识别:**

| 配置字段 | 匹配列名（不区分大小写） |
|----------|------------------------|
| IP 地址 | `IP地址`, `IP`, `ip`, `地址`, `摄像机IP`, `设备IP`, `摄像头IP` |
| 端口 | `端口`, `Port`, `port`, `端口号`, `HTTP端口` |
| 用户名 | `用户名`, `User`, `user`, `登录名`, `管理员` |
| 密码 | `密码`, `Password`, `password`, `登录密码`, `pass` |

**过滤规则:**
- 空 IP 或无效值 (`nan`, `none`, `null`) 的行跳过
- 索引规范化：`DeviceInfo.index` = 列表中的顺序索引，与 UI 映射一致
- `device.excel_row = idx + 2`（Excel 从第 2 行开始，含表头）

---

## 类: DeviceDetector

设备在线检测器，通过 Ping 扫描判断设备可达性。

### 构造函数

```python
DeviceDetector(config, log_manager, log_callback=None)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `config` | `Dict` | 配置字典（需含 `ping_concurrent`, `ping_timeout`, `ping_count` 等） |
| `log_manager` | `LogManager` | 日志管理器 |
| `log_callback` | `Callable` | GUI 日志回调函数（可选） |

### 方法

#### `detect_devices(devices, progress_callback=None, stop_callback=None) -> Tuple[int, int]`

批量 Ping 检测设备在线状态。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `devices` | `List[DeviceInfo]` | — | 待检测的设备列表 |
| `progress_callback` | `Callable` | `None` | 进度回调 `(phase, progress, stats)` |
| `stop_callback` | `Callable` | `None` | 停止检查回调（返回 `True` 时停止） |

**返回:** `(在线数, 离线数)`

**进度回调格式:**

```python
def progress_callback(phase: str, progress: float, stats: dict):
    # phase = "ping_only"
    # progress: 0.0 ~ 100.0
    # stats = {
    #     "completed": int,      # 已检测设备数
    #     "total": int,          # 总设备数
    #     "success": int,        # 在线数
    #     "failed": int,         # 离线数
    #     "devices_updated": [   # 本批更新的设备
    #         {"index": int, "status": str, "online": bool, "message": str}
    #     ]
    # }
```

**Ping 实现细节:**

- 使用 `ThreadPoolExecutor(max_workers=ping_concurrent)` 并发扫描
- Linux: `ping -c 1 -W {timeout} {ip}`
- Windows: `ping -n 1 -w {timeout} {ip}`
- 成功率判断: 返回码为 0，或输出包含成功关键字
- 离线设备自动记录到失败日志
- 每完成 10 台或全部完成时触发进度回调

**停止支持:**
- 调用 `stop_callback()` 返回 `True` 时立即停止新的检测
- 正在执行的 Ping 不会中断，但结果会被忽略

---

## 类: ConfigExecutor

批量 CGI 配置执行器，支持同步（线程池）和异步（asyncio）双模式。

### 构造函数

```python
ConfigExecutor(config, log_manager, log_callback=None, use_async=False)
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `config` | `Dict` | — | 配置字典 |
| `log_manager` | `LogManager` | — | 日志管理器 |
| `log_callback` | `Callable` | `None` | GUI 日志回调 |
| `use_async` | `bool` | `False` | 是否使用异步模式（asyncio） |

### 方法

#### `execute_batch(devices, mode="standard", exec_strategy="device_first", progress_callback=None, stop_callback=None, total_tasks=None) -> List[Dict]`

批量执行配置。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `devices` | `List[DeviceInfo]` | — | 设备列表 |
| `mode` | `str` | `"standard"` | `"standard"` 或 `"customized"` |
| `exec_strategy` | `str` | `"device_first"` | 执行策略 |
| `progress_callback` | `Callable` | `None` | 进度回调 |
| `stop_callback` | `Callable` | `None` | 停止检查 |
| `total_tasks` | `int` | `None` | 手动指定总任务数 |

**执行流程:**

```
execute_batch()
├── 严格筛选在线设备
│   ├── device.online == True
│   ├── device.status in ["在线", "等待配置", "正在配置", "执行中"]
│   └── device.selected == True
├── 跳过离线设备 → 记录失败日志
│
├── 根据 exec_strategy 选择执行路径
│   ├── device_first + use_async=False → _execute_by_device_strict()
│   ├── device_first + use_async=True  → _async_execute_by_device()
│   └── command_first                  → _execute_by_command_strict()
│
└── 返回结果列表
```

**返回格式:**

```python
[
    {
        "device": DeviceInfo,          # 设备对象
        "ip": str,                     # IP 地址
        "port": str,                   # 端口
        "success": bool,               # 是否成功（有任意命令成功）
        "total_commands": int,         # 总命令数
        "success_commands": int,       # 成功命令数
        "failed_commands": int,        # 失败命令数
        "failure_details": str,        # 失败详情
        "start_time": str,             # 开始时间 "HH:MM:SS"
        "end_time": str,               # 结束时间 "HH:MM:SS"
        "total_time": float,           # 总耗时（秒）
    },
    ...
]
```

**进度回调格式:**

```python
def progress_callback(phase: str, progress: float, stats: dict):
    # phase = "configuring"
    # stats = {
    #     "completed": int,          # 已完成任务数
    #     "total": int,              # 总任务数
    #     "success": int,            # 成功命令数
    #     "failed": int,             # 失败命令数
    #     "devices_updated": [       # 本批更新的设备状态
    #         {"index": int, "status": str, "online": bool, "message": str}
    #     ]
    # }
```

#### `stop() -> None`

停止所有配置任务：

1. 设置停止标志
2. 关闭 HTTP Session（中断阻塞请求）
3. 关闭 AsyncIOManager（中断异步请求）
4. 取消所有未完成的 Future
5. 关闭线程池

#### `_send_command(device, command, cmd_index, total_commands) -> Tuple[bool, str]`

**内部方法。** 向单台设备发送单条命令并记录 CGI 元数据日志。

### 执行策略

#### 设备优先 (`device_first`)

```
为每台在线设备分配独立线程/协程
每台设备顺序执行其所有命令
├── 适合：设备数量少但每台命令多
└── 优点：单设备独立进度，一台失败不影响其他
```

#### 命令优先 (`command_first`)

```
按命令维度并发执行
每条命令在所有在线设备上同时执行
├── 适合：设备数量多且使用相同命令
└── 优点：单命令并发度高
```

### 异步模式 (`use_async=True`)

- 使用 `AsyncIOManager` 替代同步线程池
- 命令层面的 `asyncio.Semaphore` 控制并发
- 设备级并发数 = `config_concurrent`
- 命令级并发数 = `config_concurrent * 2`
- 需要 `ConfigExecutor` 在 `event_loop` 线程中运行

### 设备状态转换图

```
未检测 ──► 在线 ──► 正在配置 ──► 执行中 ──► 成功
           │                          │
           ├── 离线                   ├── 失败
           │                          ├── 部分完成
           └── 检测超时               └── 已停止
```

### 命令解析

支持两种命令格式:

1. **标准命令:** `"VideoWidget[0].CustomTitle[0].EncodeBlend=true"`（无变量占位符）
2. **自定义命令:** `"VideoWidget[0].CustomTitle[0].Text={学校名}"`（`{变量名}` 从 Excel 变量列替换）

---

## 使用示例

### 完整流程

```python
from utils.device_manager import DeviceLoader, DeviceDetector, ConfigExecutor
from utils.log_manager import LogManager
from utils.config_manager import ConfigManager

# 1. 初始化
log_manager = LogManager(log_level="INFO")
config = ConfigManager.load_config()

# 2. 加载设备
loader = DeviceLoader(log_manager)
devices, count = loader.load_from_excel("devices.xlsx")

# 3. 检测在线
detector = DeviceDetector(config, log_manager)
online, offline = detector.detect_devices(devices)

# 4. 批量配置
executor = ConfigExecutor(config, log_manager, use_async=True)
results = executor.execute_batch(devices, mode="standard")

# 5. 统计结果
total_success = sum(r["success_commands"] for r in results)
total_failed = sum(r["failed_commands"] for r in results)
print(f"总成功: {total_success}, 总失败: {total_failed}")
```

### 带进度回调

```python
def on_progress(phase, progress, stats):
    print(f"[{phase}] {progress:.1f}% 完成: {stats['completed']}/{stats['total']}")

results = executor.execute_batch(
    devices,
    mode="standard",
    progress_callback=on_progress,
)
```

### 停止执行

```python
import threading
import signal

stop_event = threading.Event()

def on_signal(sig, frame):
    print("收到停止信号...")
    stop_event.set()

signal.signal(signal.SIGINT, on_signal)

results = executor.execute_batch(
    devices,
    stop_callback=lambda: stop_event.is_set(),
)
```

### 异步模式

```python
executor = ConfigExecutor(config, log_manager, use_async=True)
results = executor.execute_batch(
    devices,
    exec_strategy="device_first",
)
```

### 自定义模式（变量替换）

```python
# Excel 中需包含变量列，如 "学校名", "教室号"
# 命令中使用 {变量名} 占位符
config["cgi_commands"] = [
    "VideoWidget[0].CustomTitle[0].Text={学校名}",
    "VideoWidget[0].CustomTitle[0].CustomTitle={教室号}",
]

executor = ConfigExecutor(config, log_manager)
results = executor.execute_batch(devices, mode="customized")
```
