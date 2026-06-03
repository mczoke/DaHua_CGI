# cgi_reference_manager.py — CGI 参数引用管理器

## 模块概述

CGI 参数引用管理器，提供参数库查询、模块分类、参考数据维护功能。用于辅助用户了解大华设备支持的 CGI 参数及其类型、默认值。

**版本:** 9.5

## 类: CGIReferenceManager

静态方法集合，无需实例化。

### 模块定义

```python
DAHUA_MODULES = {
    "VideoWidget":    "视频叠加/OSD 配置",
    "ChannelTitle":   "通道标题",
    "VideoBoundary":  "视频边界",
    "RecordMode":     "录像模式",
    "Encode":         "编码参数",
    "System":         "系统设置",
    "Network":        "网络设置",
    "Storage":        "存储设置",
}
```

### 路径方法

| 方法 | 返回 | 说明 |
|------|------|------|
| `get_app_directory()` | `str` | 应用根目录（支持 PyInstaller 打包） |
| `get_config_directory()` | `str` | 配置目录 `{app_dir}/config/`（自动创建） |
| `get_reference_path()` | `str` | 引用文件路径 `config/cgi_reference.json` |

### 参数库

#### `get_default_reference_data() -> List[Dict]`

返回非空默认参数库，包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `param` | `str` | CGI 参数名 |
| `module` | `str` | 所属模块（对应 `DAHUA_MODULES` 的键） |
| `type` | `str` | 参数类型: `bool`, `string`, `int`, `rect` |
| `default` | `str` | 默认值（字符串形式） |
| `desc` | `str` | 中文描述 |
| `example` | `str` | 示例值 |

**预定义参数库内容:**

| 参数 | 模块 | 类型 | 默认 | 说明 |
|------|------|------|------|------|
| `VideoWidget[0].CustomTitle[0].EncodeBlend` | VideoWidget | bool | `false` | 自定义标题编码叠加 |
| `VideoWidget[0].CustomTitle[0].PreviewBlend` | VideoWidget | bool | `false` | 自定义标题预览叠加 |
| `VideoWidget[0].CustomTitle[0].Text` | VideoWidget | string | `""` | 自定义标题文字内容 |
| `VideoWidget[0].CustomTitle[0].TextAlign` | VideoWidget | int | `"0"` | 文字对齐: 0=左, 1=居中, 2=右 |
| `VideoWidget[0].CustomTitle[0].Rect` | VideoWidget | rect | `"0,0,0,0"` | 矩形区域 (x1,y1,x2,y2) |
| `VideoWidget[0].ChannelTitle.EncodeBlend` | ChannelTitle | bool | `"false"` | 通道标题编码叠加 |
| `VideoWidget[0].ChannelTitle.PreviewBlend` | ChannelTitle | bool | `"false"` | 通道标题预览叠加 |
| `VideoWidget[0].ChannelTitle.Rect` | ChannelTitle | rect | `"0,0,0,0"` | 通道标题矩形区域 |
| `VideoWidget[0].VideoBoundary` | VideoBoundary | int | `"0"` | 视频边界启用 |
| `RecordMode[0].TimeSection[0][0].Type` | RecordMode | string | `""` | 录像时段类型 |
| `Encode[0].MainFormat[0].Video.Compression` | Encode | string | `"H.264"` | 主码流编码格式 |
| `Encode[0].MainFormat[0].Video.Resolution` | Encode | string | `"1920x1080"` | 主码流分辨率 |
| `general.systemTime` | System | string | `""` | 系统时间 (GET only) |
| `Storage.Stat.UsedBytes` | Storage | int | `"0"` | 已用存储字节数 (GET only) |
| `Storage.Stat.TotalBytes` | Storage | int | `"0"` | 总存储字节数 (GET only) |

#### `get_module_categories() -> List[str]`

返回模块分类列表：`["VideoWidget", "ChannelTitle", "VideoBoundary", "RecordMode", "Encode", "System", "Network", "Storage"]`

### 加载 / 保存

#### `load_reference() -> Dict`

加载 `cgi_reference.json`，加载过程包含以下自动修复：

1. 如果文件不存在 → 创建默认引用文件并返回
2. 如果参数库为空 → 用默认参数库填充
3. 如果模块分类为空 → 用默认模块分类填充

**返回结构:**

```json
{
    "version": "9.5",
    "last_updated": "2026-06-01",
    "total_parameters": 15,
    "参数库": [ ... ],
    "模块分类": [ "VideoWidget", "ChannelTitle", ... ]
}
```

#### `save_reference(reference) -> bool`

保存引用数据到 `cgi_reference.json`。

自动维护字段：
- 自动设置 `version = "9.5"`
- 自动更新时间戳 `last_updated`
- 自动计算 `total_parameters`
- 空参数库时自动填充默认数据
- 空模块分类时自动填充默认分类

---

## 使用示例

### 加载引用数据

```python
from utils.cgi_reference_manager import CGIReferenceManager

ref = CGIReferenceManager.load_reference()

print(f"参数库版本: {ref['version']}")
print(f"参数总数: {ref['total_parameters']}")
print(f"模块分类: {ref['模块分类']}")

# 查询指定模块的参数
video_widget_params = [
    p for p in ref["参数库"] if p["module"] == "VideoWidget"
]
for p in video_widget_params:
    print(f"  {p['param']} ({p['type']}): {p['desc']}")
```

### 保存自定义引用

```python
from utils.cgi_reference_manager import CGIReferenceManager

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
