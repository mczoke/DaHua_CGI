# Task 10: Excel导入模板 + CGI批量查询功能

## 背景
V9.6-alpha 已完成GUI和Web UI基础功能。现增加两个需求：

## 需求1: Excel导入模板 + 严格校验

### 目标
1. 提供一个标准Excel模板文件供用户下载填写设备信息
2. 导入时严格校验表头列名，不匹配则报错提示，而非模糊匹配

### 具体实现

#### 1.1 模板文件
- 路径: `src/templates/device_import_template.xlsx` **（已创建，见下文"已有资源"）**
- 固定表头: `IP地址 | 端口 | 用户名 | 密码`
- 样式要求：
  - 蓝底白字表头（#4472C4）
  - 隔行变色
  - 冻结首行
  - 自动筛选
  - 附"说明"Sheet（使用说明）

#### 1.2 GUI — 下载模板按钮
- 文件: `src/full_app.py`
- 类: `DahuaConfigApp._build_ui()` (L322-L356)
- 在顶部按钮区添加"下载模板"按钮，位置在"加载 Excel"按钮旁边
- 点击后将模板文件保存到用户选择的路径（使用 filedialog.asksaveasfilename）
- 提示：在打开文件对话框时，默认文件名为 `device_import_template.xlsx`，文件类型筛选为 `Excel 文件 (*.xlsx)`

#### 1.3 GUI — 导入严格校验
- 文件: `src/utils/device_manager.py`
- 方法: `DeviceLoader._analyze_columns()`
- 添加 `strict_mode=True` 参数
  - 当 `strict_mode=True`：精确匹配表头 `IP地址 | 端口 | 用户名 | 密码`，不匹配则抛 ValueError
  - 当 `strict_mode=False`：保留现有模糊匹配逻辑（用于测试兼容）
- 方法: `DeviceLoader.load_from_excel()`
  - 调用 `_analyze_columns(df, strict_mode=True)`
  - 捕获 ValueError 后弹出 messagebox 提示用户"模板列名不匹配，请下载标准模板"
  - 不要弹出烦琐的Python报错窗口

#### 1.4 Web UI — 下载模板接口
- 文件: `src/web/app.py`
- 新增路由: `GET /api/template/download`
  - 响应: 返回 `src/templates/device_import_template.xlsx` 文件
  - `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
  - `Content-Disposition: attachment; filename=device_import_template.xlsx`

#### 1.5 Web UI — 模板下载按钮
- 文件: `src/web/templates/devices.html`
- 在"上传Excel"按钮附近添加"下载模板"按钮
  - `<a href="/api/template/download" class="btn btn-info btn-sm"><i class="bi bi-download"></i> 下载模板</a>`
  - 加提示文字：`提示：请先下载模板填写设备信息`

---

## 需求2: CGI批量查询功能

### 目标
用户给定设备IP+账号密码，批量查询CGI命令（getConfig）的返回值，结果导出为Excel。
每设备一行，横向扩展列：IP | 端口 | 账号 | 密码 | Ping状态 | 账号验证 | 命令1值 | 命令2值 | ...

### 2.1 新建查询核心模块
- 文件: `src/utils/cgi_query.py`（新建）
- 类: `CgiQueryExecutor`

#### 方法:
1. `__init__(self, config_data=None)`
   - 可选接收配置字典

2. `execute_query(self, devices: List[DeviceInfo], commands: List[str], precheck=True) -> dict`
   - **入参**:
     - `devices`: DeviceInfo对象列表（复用已有类 `from utils.device_manager import DeviceInfo`）
     - `commands`: CGI命令名称列表，如 `["Alarm", "VideoInMode", "VideoInChannel"]`
     - `precheck`: 是否执行Ping检测和账号验证（默认True）
   - **逻辑**:
     - 对每个设备，依次执行：
       a. Ping检测（使用设备的IP）
       b. 账号密码验证（尝试CGI登录）
       c. 对每个命令发 getConfig 查询
     - CGI查询格式: `http://{ip}:{port}/cgi-bin/configManager.cgi?action=getConfig&name={command}`
     - 支持变量替换: 命令可包含 `{{IP}}`, `{{port}}`, `{{username}}`, `{{password}}` 占位符
       - 示例: `http://{{IP}}:{{port}}/cgi-bin/configManager.cgi?action=getConfig&name=Alarm`
       - 替换规则: `{{IP}}` → 设备的IP, `{{port}}` → 设备的端口, 以此类推
       - 如果命令中没有变量占位符，则视为纯命令名，自动拼接标准CGI URL
   - **返回**:
     ```python
     {
         "columns": ["IP", "端口", "用户名", "密码", "Ping状态", "账号验证", "命令1名", "命令2名", ...],
         "data": [
             ["10.0.0.1", "80", "admin", "****", "✅在线", "✅验证通过", "返回值1", "返回值2", ...],
             ...
         ],
         "success": True,
         "errors": []  # 错误信息列表
     }
     ```
   - **超时处理**: 每个设备查询超时10秒
   - **Ping检测**: 参考现有 DeviceDetector 的检测逻辑，单个Ping超时默认2秒
   - **账号验证**: 尝试访问单个CGI端点（如获取设备序列号）验证账号密码正确性

3. `export_to_excel(self, data: dict, output_path: str) -> str`
   - **入参**: `execute_query()` 返回的dict
   - **逻辑**: 将data["data"]写入Excel，表头为data["columns"]
   - 表头样式：蓝底白字，冻结首行
   - 文件名自动生成：`CGI查询结果_{日期}.xlsx`
   - **返回**: 文件路径

### 2.2 GUI — 新增"CGI查询"Tab
- 文件: `src/full_app.py`
- 新增类: `QueryTab(ttk.Frame)`

#### 类结构参考AggregateReportTab (L279-L305):
```python
class QueryTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.query_executor = None  # CgiQueryExecutor
        self.query_results = None   # 查询结果dict
        self._setup_ui()
    
    def _setup_ui(self):
        # 上半部分：命令输入区
        # - Label: "CGI查询命令（每行一个）："
        # - 多行文本框（ScrolledText），高度8行
        # - 示例文本提示：
        #   # 纯命令名模式（自动拼接标准CGI URL）
        #   Alarm
        #   VideoInMode
        #   VideoInChannel
        #   # 自定义URL模式（支持{{IP}}变量替换）
        #   http://{{IP}}:{{port}}/cgi-bin/configManager.cgi?action=getConfig&name=RecordMode
        # - 按钮："开始查询"、"导出结果"
        # - 进度条
        
        # 下半部分：结果表格（Treeview）
        # - 动态列：根据查询结果自动生成列
        # - 横向滚动支持
```

#### 在DahuaConfigApp中集成:
- `src/full_app.py` L371-L378: 在Notebook添加新Tab
  ```python
  self.query_tab = QueryTab(self.nb)
  self.nb.add(self.query_tab, text='CGI查询')
  ```
- Notebook顺序: `运行日志 | 配置CGI | CGIX查询 | 聚合报表`

#### 查询执行流程:
1. 用户点击"开始查询"按钮
2. 获取当前设备列表（从 device_table 或 device_loader）
3. 读取命令输入框内容（每行一个）
4. 在新线程中执行 CgiQueryExecutor.execute_query()
5. 完成后在主线程更新结果表格
6. 支持"导出结果"按钮调用 export_to_excel()

### 2.3 Web UI — CGI查询页面
- 文件: `src/web/app.py`
- 新增路由:
  1. `GET /query` — 渲染 query.html 页面
  2. `POST /api/query/execute` — 执行CGI查询
     - 接收JSON: `{"devices": [设备索引], "commands": ["Alarm", "VideoInMode", ...]}`
     - 未指定设备时用已选中的设备
     - 返回: `{"success": true, "data": [...], "columns": [...], "count": N}`
     - 使用全局变量 `_query_executor`, `_query_result_data`, `_query_result_columns` 保存状态
  3. `GET /api/query/export` — 导出查询结果为Excel文件下载
- 文件: `src/web/templates/query.html`（新建）
  - 继承 `base.html`（暗色Bootstrap5主题）
  - 布局：
    - 左侧列 (col-md-3)：设备选择列表（复选框）
    - 右侧列 (col-md-9)：
      - 命令输入框（textarea多行）
      - "开始查询"按钮、"导出结果"按钮
      - 进度条
      - 结果表格（动态列，横向扩展）
  - 自动获取设备列表
- 文件: `src/web/templates/base.html`
  - 导航栏添加"CGI查询"项：`<a class="nav-link" href="/query"><i class="bi bi-search"></i> CGIX查询</a>`
  - 位置：在"配置执行"和"聚合报表"之间

---

## 已有资源
1. **模板文件已创建**: `src/templates/device_import_template.xlsx`（6384字节，含样表数据和说明Sheet）
2. **已有类可复用**:
   - `DeviceInfo` — `from utils.device_manager import DeviceInfo`
   - `DeviceLoader.loader_from_excel()` — 导入设备
   - `DeviceDetector` — Ping检测
   - `ConfigExecutor._send_command()` — CGI通信参考实现
3. **测试框架**: `src/tests/test_device_manager_batch1.py` 已有 `_analyze_columns` 测试

---

## 分工

### 编码 Agent（Claw-Claude / Claw-CodeX）
- 实现上述所有代码修改和新增文件
- 确保各模块间接口对齐
- 输出 README 格式的任务完成报告

### 测试 Agent（OpenClaw）
- 运行全量测试：`cd /data/DaHua_CGI && python3 -m pytest src/tests/ -v`
- 当前基线：329个测试，全部通过
- 验证新功能测试覆盖

## 验证标准
- [ ] 模板文件下载正常
- [ ] 严格校验：非模板格式的Excel导入正确报错
- [ ] 模糊匹配：旧测试兼容（strict_mode=False）
- [ ] CGI查询能正常执行并返回结果
- [ ] 查询结果Excel导出的列格式正确（每设备一行横向扩展）
- [ ] GUI新Tab显示正常
- [ ] Web UI新页面路由全部可用
- [ ] 329个测试全部通过
