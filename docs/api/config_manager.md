# config_manager.py — 配置管理模块

## 模块概述

配置管理器采用 **双源加载** 策略：YAML 优先，环境变量覆盖，兼容旧 JSON 格式。

**版本:** 9.5

## 加载优先级

```
┌─────────────────────────────────────────────────────────┐
│  1. 默认配置（硬编码） ← 最基础兜底                       │
│  2. YAML 文件（config.yaml） ← 主配置源，覆盖默认值       │
│  3. JSON 文件（dahua_config.json） ← 兼容旧的 JSON 配置   │
│     只覆盖 YAML 中没有的字段或等于默认值的字段              │
│  4. 环境变量 ← 最高优先级，可覆盖一切                      │
└─────────────────────────────────────────────────────────┘
```

## 类: ConfigManager

静态方法集合，无需实例化。

### 路径方法

| 方法 | 返回 | 说明 |
|------|------|------|
| `get_app_directory()` | `str` | 应用根目录（支持 PyInstaller 打包） |
| `get_config_directory()` | `str` | 配置目录 `{app_dir}/config/`（自动创建） |
| `get_config_yaml_path()` | `str` | YAML 配置路径 `config/config.yaml` |
| `get_config_json_path()` | `str` | JSON 配置路径 `config/dahua_config.json` |

### 默认值

#### `get_default_config() -> Dict[str, Any]`

返回默认配置字典：

| 键 | 类型 | 默认值 | 说明 |
|----|------|--------|------|
| `cgi_commands` | `List[str]` | (见下) | CGI 命令列表 |
| `variable_mappings` | `Dict` | `{}` | 变量映射 |
| `timeout` | `int` | `30` | 请求超时(秒) |
| `verify_ssl` | `bool` | `False` | SSL 验证（默认关闭兼容旧设备） |
| `max_retries` | `int` | `3` | 最大重试次数 |
| `auth_method` | `str` | `"digest"` | 认证方式 |
| `ping_timeout` | `int` | `3` | Ping 超时(秒) |
| `ping_count` | `int` | `1` | Ping 次数 |
| `ping_concurrent` | `int` | `150` | Ping 并发数 |
| `config_concurrent` | `int` | `80` | 配置并发数 |
| `exec_strategy` | `str` | `"device_first"` | 执行策略: `device_first` / `command_first` |
| `enable_precheck` | `bool` | `True` | 前置检测 |
| `auto_skip_offline` | `bool` | `True` | 自动跳过离线设备 |
| `default_mode` | `str` | `"standard"` | 默认模式: `standard` / `customized` |
| `log_level` | `str` | `"INFO"` | 日志级别 |
| `auto_save_results` | `bool` | `True` | 自动保存结果 |
| `export_format` | `str` | `"excel"` | 导出格式 |

#### `get_default_cgi_commands() -> List[str]`

默认 CGI 命令（大华摄像头自定义标题设置）：

```python
[
    "VideoWidget[0].CustomTitle[0].EncodeBlend=true",
    "VideoWidget[0].CustomTitle[0].PreviewBlend=true",
    "VideoWidget[0].CustomTitle[0].Rect[0]=5207",
    "VideoWidget[0].CustomTitle[0].Rect[1]=6631",
    "VideoWidget[0].CustomTitle[0].Rect[2]=7828",
    "VideoWidget[0].CustomTitle[0].Rect[3]=7069",
    "VideoWidget[0].CustomTitle[0].Text=日照职业技术学院天台山校区",
    "VideoWidget[0].CustomTitle[0].TextAlign=2",
]
```

### 加载方法

#### `load_config() -> Dict[str, Any]`

完整加载流程（YAML → JSON 补充 → 环境变量覆盖 → 校验修正）。

#### `save_config(config) -> bool`

保存配置到 `dahua_config.json`。

### 内部方法

| 方法 | 说明 |
|------|------|
| `_apply_env_overrides(config)` | 环境变量覆盖（大写+下划线命名） |
| `_validate_and_fix_config(config, defaults)` | 校验并修正配置值 |

### 环境变量映射

| 环境变量 | 配置键 | 类型 |
|----------|--------|------|
| `TIMEOUT` | `timeout` | int |
| `PING_TIMEOUT` | `ping_timeout` | int |
| `PING_COUNT` | `ping_count` | int |
| `PING_CONCURRENT` | `ping_concurrent` | int (上限200) |
| `CONFIG_CONCURRENT` | `config_concurrent` | int (上限100) |
| `MAX_RETRIES` | `max_retries` | int |
| `LOG_LEVEL` | `log_level` | str |
| `EXPORT_FORMAT` | `export_format` | str |
| `AUTH_METHOD` | `auth_method` | str |
| `VERIFY_SSL` | `verify_ssl` | bool |

环境变量值自动类型转换：`"true"`/`"1"`/`"yes"` → bool；数字自动转为 int/float。

---

## 使用示例

### 加载配置

```python
from utils.config_manager import ConfigManager

config = ConfigManager.load_config()
print(f"超时: {config['timeout']}s")
print(f"日志级别: {config['log_level']}")
print(f"CGI 命令数: {len(config['cgi_commands'])}")
```

### 覆盖配置

```bash
# 环境变量覆盖
export LOG_LEVEL=DEBUG
export PING_CONCURRENT=200
export VERIFY_SSL=true
python main.py
```

### 自定义配置 (config.yaml)

```yaml
# config/config.yaml
timeout: 60
verify_ssl: false
ping_concurrent: 100
config_concurrent: 50
log_level: DEBUG
exec_strategy: device_first
cgi_commands:
  - "VideoWidget[0].CustomTitle[0].EncodeBlend=true"
  - "VideoWidget[0].CustomTitle[0].PreviewBlend=true"
```

### 保存配置

```python
from utils.config_manager import ConfigManager

config = ConfigManager.load_config()
config["timeout"] = 45
ConfigManager.save_config(config)
```

### 获取目录

```python
print(ConfigManager.get_app_directory())     # /data/DaHua_CGI/src
print(ConfigManager.get_config_directory())   # /data/DaHua_CGI/src/config
```

---

## 约束说明

- `ping_concurrent` 上限 200
- `config_concurrent` 上限 100
- 不支持 YAML 时使用 JSON 格式（`yaml` 包未安装）
- 保存始终使用 JSON 格式以保证向下兼容
