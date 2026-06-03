# log_manager.py — 日志管理模块

## 模块概述

日志管理器提供四层日志功能：

1. **Python logging 系统** — 级别控制 + 100MB 轮转文件
2. **详细日志文件** — `detailed_*.log`，记录详细操作
3. **失败日志文件** — `failures_*.log`，记录配置失败详情
4. **CGI 元数据日志** — 记录请求/响应头、URL、参数等调试信息
5. **Excel 结果导出** — 导出配置结果到 XLSX

**版本:** 9.5

## 类: LogManager

### 构造函数

```python
LogManager(log_level: str = "INFO")
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `log_level` | `str` | `"INFO"` | Python logging 级别，可选 `DEBUG`, `INFO`, `WARNING`, `ERROR` |

**初始化时自动创建:**
- `logs/` 目录（如不存在的）
- Python logging + 100MB 轮转 handler
- `detailed_{timestamp}.log` — 详细日志
- `failures_{timestamp}.log` — 失败日志
- `results_{timestamp}.xlsx` — 结果导出（空初始化）

### 常量

| 常量 | 值 | 说明 |
|------|-----|------|
| `MAX_RESPONSE_BYTES` | `1024` | CGI 响应截断阈值（超过此值的响应体自动截断） |

### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `app_dir` | `str` | 应用根目录 |
| `log_dir` | `str` | 日志目录 `{app_dir}/logs/` |
| `detailed_log_file` | `Optional[str]` | 详细日志文件路径 |
| `failure_log_file` | `Optional[str]` | 失败日志文件路径 |
| `excel_result_file` | `Optional[str]` | Excel 结果文件路径 |

### 基础日志

#### `log_detailed(message, level="INFO") -> None`

写入详细日志文件 + Python logging。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `message` | `str` | — | 日志消息 |
| `level` | `str` | `"INFO"` | 日志级别 |

**输出格式:**

```
[2026-06-01 14:30:00] [INFO] 开始配置设备 192.168.1.100
```

两个输出目标：
1. 追加到 `detailed_{timestamp}.log`
2. 同步到 Python `logging` 系统（`app_{timestamp}.log` + 100MB 轮转）

#### `log_failure(device_info, error_message, command="") -> None`

记录失败日志。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `device_info` | `object` / `str` | — | 设备对象（含 `.ip` 属性）或 IP 字符串 |
| `error_message` | `str` | — | 错误描述 |
| `command` | `str` | `""` | 失败的命令（可选） |

**输出格式:**

```
[2026-06-01 14:30:05] 设备 192.168.1.100 失败: HTTP 401: Unauthorized
```

### CGI 元数据日志

#### `log_cgi_request(device_ip, command_index, total_commands, full_url, auth_type, headers, method, raw_command) -> None`

记录详细的 CGI 请求元数据。

| 参数 | 类型 | 说明 |
|------|------|------|
| `device_ip` | `str` | 设备 IP |
| `command_index` | `int` | 命令序号 |
| `total_commands` | `int` | 总命令数 |
| `full_url` | `str` | 完整请求 URL |
| `auth_type` | `str` | 认证方式 |
| `headers` | `Dict` | 请求头（>2KB 截断） |
| `method` | `str` | HTTP 方法（默认 GET） |
| `raw_command` | `str` | 原始命令 |

**日志格式:**

```
[2026-06-01 14:30:00] [CGI_REQUEST] 设备 192.168.1.100 请求 1/8
  请求URL: http://192.168.1.100:80/cgi-bin/configManager.cgi?action=setConfig&...
  原始命令: VideoWidget[0].CustomTitle[0].EncodeBlend=true
  请求方法: GET
  认证方式: digest
  请求头: {'Accept-Encoding': ...}
```

#### `log_cgi_response(device_ip, status_code, response_time, response_headers, response_body, success, raw_command) -> None`

记录详细的 CGI 响应元数据。

**截断规则：**
- 响应体 > 1KB 时自动截断（由 `MAX_RESPONSE_BYTES` 控制）
- 响应头 > 2KB 时截断

### 原始数据日志

#### `log_raw_request(device_ip, command_index, total_commands, full_url, raw_command, auth_type, headers, method) -> None`

记录原始请求数据（DEBUG 级别，用于调试）。

#### `log_raw_response(device_ip, status_code, response_time, response_headers, response_body, raw_command) -> None`

记录原始响应数据（DEBUG 级别）。

**截断行为：**
- 响应体 > 1KB 时截断并标注 `(截断)`
- 日志级别为 DEBUG
- 日志条目包含原始响应大小和截断后大小

### 文件操作

#### `open_failure_logs() -> bool`

打开失败日志文件（平台相关：xdg-open/open/start）。

#### `open_log_directory() -> bool`

打开日志目录。

#### `export_excel_results(devices, excel_source_file) -> Optional[str]`

导出配置结果到 Excel。输出文件 → `logs/results_{timestamp}.xlsx`。

| 参数 | 类型 | 说明 |
|------|------|------|
| `devices` | `List[DeviceInfo]` | 设备列表 |
| `excel_source_file` | `str` | 源 Excel 文件路径 |

---

## 日志文件结构

```
src/
├── logs/
│   ├── app_20260601_143000.log    # Python logging（100MB 轮转，保留5份）
│   ├── detailed_20260601_143000.log  # 详细操作日志
│   ├── failures_20260601_143000.log  # 失败日志
│   └── results_20260601_143000.xlsx  # 结果导出
└── ...
```

### Python logging 配置

- 文件路径: `logs/app_{timestamp}.log`
- 轮转策略: `RotatingFileHandler(maxBytes=100MB, backupCount=5)`
- 格式: `"2026-06-01 14:30:00 [INFO] 消息"`
- 级别: 由构造函数 `log_level` 参数控制

### 详细日志示例

```
[2026-06-01 14:30:00] [INFO] 开始Ping检测 150 台设备
[2026-06-01 14:30:03] [INFO] 设备 192.168.1.100 Ping成功
[2026-06-01 14:30:05] [INFO] 开始配置 120 台符合条件的在线设备
[2026-06-01 14:30:05] [INFO] 总配置任务数: 960
[2026-06-01 14:30:06] [CGI_REQUEST] 192.168.1.100 请求 1/8 digest
[2026-06-01 14:30:06] [SUCCESS] [CGI_RESPONSE] 192.168.1.100 响应 200 0.35s
[2026-06-01 14:30:10] [WARNING] 设备 192.168.1.200 失败: HTTP 401: Unauthorized
[2026-06-01 14:35:00] [INFO] 配置完成: 856/960命令执行完成 (89.2%完成率)
```

---

## 使用示例

### 初始化

```python
from utils.log_manager import LogManager

# DEBUG 级别
log_manager = LogManager(log_level="DEBUG")

# INFO 级别（默认）
log_manager = LogManager()

# 生产环境
log_manager = LogManager(log_level="WARNING")
```

### 记录 CGI 请求

```python
log_manager.log_cgi_request(
    device_ip="192.168.1.100",
    command_index=1,
    total_commands=8,
    full_url="http://192.168.1.100:80/cgi-bin/configManager.cgi?action=setConfig&...",
    auth_type="digest",
    headers={"Accept-Encoding": "gzip"},
    raw_command="VideoWidget[0].CustomTitle[0].EncodeBlend=true",
)
```

### 记录 CGI 响应

```python
log_manager.log_cgi_response(
    device_ip="192.168.1.100",
    status_code=200,
    response_time=0.35,
    response_headers={"Server": "Dahua"},
    response_body="result=0\r\nOK",
    success=True,
)
```

### 记录原始响应（调试用）

```python
# 自动截断超过 1KB 的响应体
response_body = "result=0\r\n" * 500  # ~6KB
log_manager.log_raw_response(
    device_ip="192.168.1.100",
    status_code=200,
    response_time=0.35,
    response_headers={},
    response_body=response_body,
)
# 日志中响应体截断为前 1024 字节，标注 "(截断)"
```

### 记录失败

```python
log_manager.log_failure(
    device, "HTTP 401: 认证失败",
    command="VideoWidget[0].CustomTitle[0].EncodeBlend=true"
)
```

### 导出 Excel 结果

```python
devices = [device1, device2, device3]
excel_path = log_manager.export_excel_results(devices, "devices.xlsx")
```

### 打开日志

```python
log_manager.open_failure_logs()   # 打开失败日志文件
log_manager.open_log_directory()  # 打开日志目录
```
