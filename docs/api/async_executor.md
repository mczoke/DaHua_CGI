# async_executor.py — 异步 CGI 请求执行器

## 模块概述

基于 `requests` 库的 CGI 请求执行器。因 `aiohttp` 对 HTTP Digest 认证支持不完善，本项目采用 **同步 `requests` + `asyncio` 线程池** 方案实现并发。

**版本:** 2.0 (2026-06-01)

## 类图

```
SyncRequestsExecutor
    └──# _session: requests.Session (lazy, 带重试)
    │
    ├── send_command_sync(device, command) → Tuple[bool, str, str, dict, str]
    ├── close()
    └── _build_simple_params(command) → str
    └── _build_dahua_params(command) → str

AsyncExecutor (async context manager)
    ├── # sync_executor: SyncRequestsExecutor
    ├── # _thread_pool: ThreadPoolExecutor(max_workers=50)
    ├── send_command_async(device, command) → Tuple[...]
    ├── async close()
    └── async __aenter__() / __aexit__()

AsyncIOManager
    ├── # sync_executor: SyncRequestsExecutor
    ├── # _thread_pool: ThreadPoolExecutor(max_workers=50)
    ├── send_command_async(device, command) → Tuple[...]
    ├── send_command(device, command) → Tuple[...]  (同步兼容)
    ├── run_coroutine(coro) → Any                   (兼容接口)
    └── close(wait=True)
```

## 类: SyncRequestsExecutor

同步 HTTP 请求执行器，内部维护带重试机制的 `requests.Session`。

### 构造函数

```python
SyncRequestsExecutor(verify_ssl: bool = True, request_timeout: int = 30)
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `verify_ssl` | `bool` | `True` | SSL 证书验证（生产环境建议保持 True） |
| `request_timeout` | `int` | `30` | 请求超时秒数 |

### 方法

#### `send_command_sync(device, command) -> Tuple[bool, str, str, Dict, str]`

同步向设备发送 CGI 命令。

**参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| `device` | `DeviceInfo` | 设备信息对象，需包含 `.ip`, `.port`, `.username`, `.password` |
| `command` | `dict` 或 `str` | 命令。支持字典格式 `{"action": "setConfig", "param": {...}}` 或字符串格式 `"VideoWidget[0].CustomTitle[0].EncodeBlend=true"` |

**返回:**

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | `bool` | 请求是否成功 |
| `response_text` | `str` | 响应正文 |
| `status` | `str` | 状态码 `"SUCCESS"` / `"FAILED"` |
| `headers` | `Dict` | 响应头字典 |
| `error` | `str` | 错误信息（成功时为空） |

**重试机制:**

- 重试次数: 3
- 退避因子: 0.5 (指数退避)
- 可重试状态码: 429, 500, 502, 503, 504
- 可重试方法: GET, POST

**认证方式:**

- HTTP Digest 认证（使用 `requests.auth.HTTPDigestAuth`）
- 自动拼接 CGI URL: `http://{ip}:{port}/cgi-bin/configManager.cgi`

#### `close() -> None`

关闭底层的 `requests.Session`，释放连接池。

#### `_build_simple_params(command) -> str`

构造简化的 URL 查询参数。

#### `_build_dahua_params(command) -> str`

构造大华设备标准参数格式（扁平化参数处理）。

---

## 类: AsyncExecutor

异步执行器，通过线程池将同步请求转换为异步协程。

### 构造函数

```python
AsyncExecutor(
    timeout: int = 30,
    verify_ssl: bool = True,
    max_connections: int = 100,
    auth_method: str = 'digest',
)
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `timeout` | `int` | `30` | 请求超时秒数 |
| `verify_ssl` | `bool` | `True` | SSL 证书验证 |
| `max_connections` | `int` | `100` | 连接池大小 |
| `auth_method` | `str` | `'digest'` | 认证方式 |

### 方法

#### `async send_command_async(device, command) -> Tuple[...]`

在 `ThreadPoolExecutor(max_workers=50)` 中执行同步请求。

**参数/返回值:** 同 `SyncRequestsExecutor.send_command_sync()`。

#### `async close() -> None`

优雅关闭：
1. 设置 `_closed = True`
2. 关闭线程池（`shutdown(wait=True)`）
3. 关闭 `sync_executor`

#### `async __aenter__() / __aexit__()`

支持 `async with` 语法：

```python
async with AsyncExecutor(timeout=15) as ex:
    ok, msg, status, headers, error = await ex.send_command_async(device, cmd)
```

### 辅助函数

#### `async send_multiple_commands(device, commands, timeout=10) -> List[Tuple[bool, str]]`

并发发送多条命令到同一设备。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `device` | `DeviceInfo` | — | 目标设备 |
| `commands` | `List` | — | 命令列表 |
| `timeout` | `int` | `10` | 超时秒数 |

---

## 类: AsyncIOManager

兼容旧接口的异步管理器（`device_manager.py` 中 `ConfigExecutor` 使用此接口）。

### 构造函数

同 `AsyncExecutor`。

### 方法

#### `async send_command_async(device, command, use_url_auth=False) -> Tuple[...]`

在 `ThreadPoolExecutor(max_workers=50)` 中执行同步请求。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `device` | `DeviceInfo` | — | 设备信息 |
| `command` | `dict`/`str` | — | 命令 |
| `use_url_auth` | `bool` | `False` | 是否使用 URL 内嵌认证（旧兼容模式） |

#### `send_command(device, command) -> Tuple[...]`

同步兼容包装器。自动检测事件循环状态：
- 如果事件循环未运行 → 直接 `asyncio.run()`
- 如果事件循环正在运行 → 使用线程池执行

#### `run_coroutine(coro) -> Any`

运行协程（兼容原有同步接口）。

#### `close(wait=True) -> None`

关闭管理器。

---

## 使用示例

### 同步发送

```python
from utils.async_executor import SyncRequestsExecutor

executor = SyncRequestsExecutor(verify_ssl=False)
device = DeviceInfo(ip="192.168.1.100", port="80", username="admin", password="admin123")

ok, text, status, headers, error = executor.send_command_sync(
    device, "VideoWidget[0].CustomTitle[0].EncodeBlend=true"
)
```

### 异步发送

```python
import asyncio
from utils.async_executor import AsyncIOManager

manager = AsyncIOManager(timeout=30)

async def send():
    ok, text, status, headers, error = await manager.send_command_async(
        device, {"action": "setConfig", "param": {"EncodeBlend": "true"}}
    )
    print(f"成功: {ok}, 响应: {text}")
```

### AsyncIOManager 同步调用

```python
manager = AsyncIOManager(timeout=30)
ok, msg, status, headers, err = manager.send_command(device, command)
```

### 并发发送多条命令

```python
from utils.async_executor import send_multiple_commands

commands = [
    "VideoWidget[0].CustomTitle[0].EncodeBlend=true",
    "VideoWidget[0].CustomTitle[0].PreviewBlend=true",
]
results = asyncio.run(send_multiple_commands(device, commands, timeout=10))
```

---

## 内部实现细节

### 认证流程

```
requests.get(url, auth=HTTPDigestAuth(username, password))
    1. 首次请求无认证头 → 服务器返回 401 + WWW-Authenticate
    2. requests 自动计算 Digest 摘要
    3. 重发请求带上 Authorization 头
```

### 线程池

```
ThreadPoolExecutor(max_workers=50, thread_name_prefix="async_executor")
    └── 惰性创建，关闭时 shutdown(wait=True)
```

### Session 重试适配器

```
HTTPAdapter(pool_connections=100, pool_maxsize=100)
    └── Retry(total=3, backoff_factor=0.5, status_forcelist=[429,500,502,503,504])
```

### 命令参数构造

支持两种命令格式：

1. **字符串格式:** `"VideoWidget[0].CustomTitle[0].EncodeBlend=true"` → 自动解析为 `setConfig`
2. **字典格式:**

```python
{
    "action": "setConfig",
    "param": {
        "VideoWidget[0].CustomTitle[0].EncodeBlend": "true"
    }
}
```
