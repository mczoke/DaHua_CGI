# cgi_reference_manager.py — CGI 参数引用管理器

## 模块概述

CGI 参数引用管理器，提供参数库查询、CGI 命令参考、模块分类、参考数据维护功能。用于辅助了解大华设备支持的 CGI 命令及其参数、返回值说明。

**版本:** 10.0 (2026-06-03)

### 新增内容 (v10.0)
- **CGI 命令参考** — 告警/智能分析/设备管理共 11 条命令，含参数列表、返回值说明
- **参数库扩展** — 新增 Alarm / SmartAnalysis / DeviceConfig 三模块共 23 个参数
- **查询方法** — `get_commands_by_module()`, `get_command()`, `search_commands()`, `search_params()` 等

---

## 类: CGIReferenceManager

静态方法集合，无需实例化。

### 模块定义

```python
DAHUA_MODULES = {
    "VideoWidget":      "视频叠加/OSD 配置",
    "ChannelTitle":     "通道标题",
    "VideoBoundary":    "视频边界",
    "RecordMode":       "录像模式",
    "Encode":           "编码参数",
    "System":           "系统设置",
    "Network":          "网络设置",
    "Storage":          "存储设置",
    "Alarm":            "告警管理",           # ← NEW
    "SmartAnalysis":    "智能分析",           # ← NEW
    "DeviceConfig":     "设备配置管理",        # ← NEW
}
```

---

### CGI 命令参考

#### 数据结构

```python
CGI_COMMANDS = [
    {
        "command": "GetAlarmRecord",        # 命令名称
        "module": "Alarm",                  # 所属模块
        "action": "getAlarmRecord",         # CGI action 参数值
        "method": "GET",                    # HTTP 方法
        "description": "获取告警记录",       # 中文描述
        "url_example": "/cgi-bin/eventManager.cgi?action=...",  # 示例 URL
        "params": [                         # 参数列表
            {
                "name": "pageNo",
                "type": "int",
                "required": True,
                "default": "1",
                "desc": "页码",
            },
            ...
        ],
        "returns": {                        # 返回值说明
            "format": "XML | table | text",
            "fields": [
                {"name": "alarmRecord", "desc": "告警记录列表"},
                ...
            ],
        },
    },
    ...
]
```

#### 预定义命令列表

| 命令 | 模块 | Action | 描述 | 参数数 |
|------|------|--------|------|--------|
| GetAlarmRecord | Alarm | `getAlarmRecord` | 获取告警记录 | 6 |
| GetAlarmConfig | Alarm | `getConfig` | 获取告警配置 | 1 |
| SetAlarmConfig | Alarm | `setConfig` | 设置告警配置 | 7 |
| GetEventType | Alarm | `getEventType` | 获取支持的事件类型 | 0 |
| GetSmartAnalysis | SmartAnalysis | `getConfig` | 获取智能分析配置 | 1 |
| GetFaceInfo | SmartAnalysis | `getFaceInfo` | 获取人脸检测信息 | 3 |
| GetVideoAnalyze | SmartAnalysis | `getConfig` | 获取视频分析配置 | 1 |
| GetDeviceConfig | DeviceConfig | `getConfig` | 获取设备通用配置 | 1 |
| SetDeviceConfig | DeviceConfig | `setConfig` | 设置设备通用配置 | 4 |
| GetNetworkConfig | Network | `getConfig` | 获取网络配置 | 1 |
| GetTimeConfig | System | `getConfig` | 获取时间配置 | 1 |

##### 告警命令详情

- **GetAlarmRecord**: `/cgi-bin/eventManager.cgi?action=getAlarmRecord` — 查询告警记录，支持分页和时间范围过滤
- **GetAlarmConfig**: `/cgi-bin/configManager.cgi?action=getConfig&name=AlarmOut` — 获取报警输出/移动侦测等配置
- **SetAlarmConfig**: `/cgi-bin/configManager.cgi?action=setConfig` — 设置报警输出模式、视频遮挡/丢失检测等
- **GetEventType**: `/cgi-bin/eventManager.cgi?action=getEventType` — 查询设备支持的全部事件类型

##### 智能分析命令详情

- **GetSmartAnalysis**: `/cgi-bin/configManager.cgi?action=getConfig&name=SmartAnalysis` — 获取智能分析启用状态和类型
- **GetFaceInfo**: `/cgi-bin/faceManager.cgi?action=getFaceInfo` — 获取人脸检测信息（需设备支持）
- **GetVideoAnalyze**: `/cgi-bin/configManager.cgi?action=getConfig&name=VideoAnalyze` — 获取视频分析规则配置

##### 设备管理命令详情

- **GetDeviceConfig**: `/cgi-bin/configManager.cgi?action=getConfig&name=General` — 获取序列号、设备名、语言等
- **SetDeviceConfig**: `/cgi-bin/configManager.cgi?action=setConfig` — 修改设备名、语言、视频制式等
- **GetNetworkConfig**: `/cgi-bin/configManager.cgi?action=getConfig&name=Network` — 获取 IP/掩码/网关/DNS/DHCP
- **GetTimeConfig**: `/cgi-bin/configManager.cgi?action=getConfig&name=General.Time` — 获取时区/同步类型/NTP 配置

---

### 路径方法

| 方法 | 返回 | 说明 |
|------|------|------|
| `get_app_directory()` | `str` | 应用根目录（支持 PyInstaller 打包） |
| `get_config_directory()` | `str` | 配置目录 `{app_dir}/config/`（自动创建） |
| `get_reference_path()` | `str` | 引用文件路径 `config/cgi_reference.json` |

---

### 参数库

#### `get_default_reference_data() -> List[Dict]`

返回非空默认参数库（共约 38 个参数），包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `param` | `str` | CGI 参数名 |
| `module` | `str` | 所属模块（对应 `DAHUA_MODULES` 的键） |
| `type` | `str` | 参数类型: `bool`, `string`, `int`, `rect` |
| `default` | `str` | 默认值（字符串形式） |
| `desc` | `str` | 中文描述 |
| `example` | `str` | 示例值 |

**模块分布（新增加粗）：**

| 模块 | 参数数 | 说明 |
|------|--------|------|
| VideoWidget | 5 | 视频叠加/OSD |
| ChannelTitle | 3 | 通道标题 |
| VideoBoundary | 1 | 视频边界 |
| RecordMode | 1 | 录像模式 |
| Encode | 2 | 编码参数 |
| System | 3 | 系统设置 |
| Storage | 2 | 存储设置 |
| **Alarm** | **8** | **告警管理** |
| **SmartAnalysis** | **5** | **智能分析** |
| **DeviceConfig** | **4** | **设备配置管理** |
| **Network** | **4** | **网络参数** |

**新增参数列表：**

| 参数 | 模块 | 类型 | 说明 |
|------|------|------|------|
| `AlarmOut[0].Mode` | Alarm | int | 告警输出模式 |
| `AlarmOut[0].Channel` | Alarm | int | 告警输出通道 |
| `AlarmOut[0].State` | Alarm | int | 告警输出状态 |
| `MotionDetect[0].Enable` | Alarm | bool | 移动侦测启用 |
| `MotionDetect[0].Sensitivity` | Alarm | int | 移动侦测灵敏度 |
| `VideoBlind[0].Enable` | Alarm | bool | 视频遮挡检测启用 |
| `VideoBlind[0].Sensitivity` | Alarm | int | 视频遮挡灵敏度 |
| `VideoLoss[0].Enable` | Alarm | bool | 视频丢失检测启用 |
| `SmartAnalysis[0].Enable` | SmartAnalysis | bool | 智能分析启用 |
| `SmartAnalysis[0].EventType` | SmartAnalysis | string | 事件类型 |
| `VideoAnalyze[0].Enable` | SmartAnalysis | bool | 视频分析启用 |
| `VideoAnalyze[0].DetectType` | SmartAnalysis | string | 检测类型 |
| `VideoAnalyze[0].Rule[0].Enable` | SmartAnalysis | bool | 规则启用 |
| `General.MachineName` | DeviceConfig | string | 设备名称 |
| `General.Language` | DeviceConfig | string | 系统语言 |
| `General.VideoFormat` | DeviceConfig | string | 视频制式 |
| `General.SerialNo` | DeviceConfig | string | 设备序列号 |
| `Network.IPAddress` | Network | string | IP地址 |
| `Network.SubnetMask` | Network | string | 子网掩码 |
| `Network.Gateway` | Network | string | 默认网关 |
| `Network.DNS` | Network | string | DNS服务器 |
| `Network.DHCP` | Network | bool | DHCP启用 |
| `General.Time.TimeZone` | System | string | 时区 |
| `General.Time.SyncType` | System | string | 时间同步类型 |
| `General.Time.NTPServer` | System | string | NTP服务器 |

---

### 查询方法（v10.0 新增）

| 方法 | 返回 | 说明 |
|------|------|------|
| `get_commands_by_module(module) -> List[Dict]` | `List[Dict]` | 按模块查询所有 CGI 命令 |
| `get_command(command_name) -> Optional[Dict]` | `Dict` / `None` | 按命令名查询单条命令 |
| `get_params_by_module(module) -> List[Dict]` | `List[Dict]` | 按模块查询参数 |
| `search_commands(keyword) -> List[Dict]` | `List[Dict]` | 模糊搜索命令（名/描述） |
| `search_params(keyword) -> List[Dict]` | `List[Dict]` | 模糊搜索参数（参数名/描述） |
| `get_command_list() -> List[Dict]` | `List[Dict]` | 返回完整命令列表 |

---

### 加载 / 保存

#### `load_reference() -> Dict`

加载 `cgi_reference.json`，加载过程包含以下自动修复：

1. 如果文件不存在 → 创建默认引用文件并返回
2. 如果参数库为空 → 用默认参数库填充
3. 如果 CGI 命令参考为空 → 用默认命令列表填充
4. 如果模块分类为空 → 用默认模块分类填充

**返回结构:**

```json
{
    "version": "10.0",
    "last_updated": "2026-06-03",
    "total_parameters": 38,
    "total_commands": 11,
    "参数库": [ ... ],
    "CGI命令参考": [ ... ],
    "模块分类": [ "VideoWidget", "ChannelTitle", ..., "DeviceConfig" ]
}
```

#### `save_reference(reference) -> bool`

保存引用数据到 `cgi_reference.json`。

自动维护字段：
- 自动设置 `version = "10.0"`
- 自动更新时间戳 `last_updated`
- 自动计算 `total_parameters` 和 `total_commands`
- 空参数库时自动填充默认数据
- 空命令参考时自动填充默认命令列表
- 空模块分类时自动填充默认分类

---

## 使用示例

### 加载引用数据

```python
from utils.cgi_reference_manager import CGIReferenceManager

ref = CGIReferenceManager.load_reference()

print(f"参数库版本: {ref['version']}")
print(f"参数总数: {ref['total_parameters']}")
print(f"CGI 命令数: {ref['total_commands']}")
print(f"模块分类: {ref['模块分类']}")
```

### 查询告警相关命令

```python
# 查询所有告警命令
alarm_cmds = CGIReferenceManager.get_commands_by_module("Alarm")
for cmd in alarm_cmds:
    print(f"  {cmd['command']} — {cmd['description']}")
    for p in cmd['params']:
        print(f"    {p['name']} ({p['type']}, {'必填' if p['required'] else '可选'}): {p['desc']}")

# 查询单条命令
cmd = CGIReferenceManager.get_command("GetAlarmRecord")
if cmd:
    print(f"URL: {cmd['url_example']}")
    print(f"返回格式: {cmd['returns']['format']}")
```

### 搜索功能

```python
# 搜索命令
results = CGIReferenceManager.search_commands("告警")
for cmd in results:
    print(f"{cmd['command']}: {cmd['description']}")

# 搜索参数
results = CGIReferenceManager.search_params("灵敏度")
for p in results:
    print(f"{p['param']} — {p['desc']}")
```

### 按模块查询参数

```python
alarm_params = CGIReferenceManager.get_params_by_module("Alarm")
for p in alarm_params:
    print(f"  {p['param']} ({p['type']}): {p['desc']}")
```

### 保存自定义引用

```python
ref = CGIReferenceManager.load_reference()
ref["参数库"].append({
    "param": "VideoWidget[0].CustomTitle[0].FontSize",
    "module": "VideoWidget",
    "type": "int",
    "default": "18",
    "desc": "自定义标题字体大小",
    "example": "24",
})
CGIReferenceManager.save_reference(ref)
```

### 获取目录

```python
print(CGIReferenceManager.get_reference_path())
# /data/DaHua_CGI/src/config/cgi_reference.json
```
