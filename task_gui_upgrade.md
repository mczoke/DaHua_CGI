# TASK: GUI 维护升级 — Claw-Claude

## 背景
DaHua_CGI 项目已完 Task1-9，全量 322/322 测试通过。
当前 GUI (`src/full_app.py`) 标题还是 V9.5，需要升级到 V9.6-alpha 并对接 Task9 新功能。

## 当前 GUI 结构 (630行)
- `src/full_app.py`：DahuaConfigApp(Tk) 主窗口
  - DeviceTableFrame(ttk.Frame)：设备表格（加载/Ping/选中）
  - LogPanel(ttk.Frame)：日志面板
  - ConfigTab(ttk.Frame)：配置选项卡（CGI命令/超时/并发/执行策略等）
  - progress_bar + progress_text_var：进度条
  - 按钮：加载Excel / Ping检测 / 开始配置 / 停止 / 保存配置 / 重载配置 / 默认配置 / 查看失败 / 日志目录

## 测试文件 (Mock tkinter 无显示器兼容)
- `src/tests/test_full_app.py`：33 个测试，全部通过

## 需要做的事

### 1. 版本号更新
- `full_app.py` 第4行: `V9.5 → V9.6-alpha`
- `full_app.py` 第280行: `'DaHua CGI 批量配置 - V9.5' → 'DaHua CGI 批量配置 - V9.6-alpha'`

### 2. 对接 Task9 — 聚合报表展示
Task9 新增了 `src/utils/aggregate_collector.py`（AggregateResultCollector）
功能：执行完成后生成跨设备聚合报表（按设备维度/命令维度统计）

需要在 GUI 增加的：
- 配置完成后，调用 `AggregateResultCollector` 生成报表
- 新增一个 tab（在 Notebook 中），显示聚合报表
- 报表内容：成功/失败数、按命令统计、按设备统计
- 提供"导出报表"按钮（CSV/Excel）

### 3. 现有功能兼容性检查
GUI 的 `execute_batch` 调用已兼容 Task9 的 V2 签名（已在 Mock 测试验证）
需要确认真实环境下：
- 设备表格状态更新正常工作
- 停止按钮功能正常
- 进度条显示正常

### 4. GUI 测试更新
更新 `test_full_app.py`，确保新增的聚合报表功能有测试覆盖
运行 `pytest src/tests/test_full_app.py -v` 确认全部通过

## 项目路径与命令
- 项目：`/data/DaHua_CGI/`
- Python：`/home/rzpt/.conda/envs/hermes/bin/python3`
- 测试运行：`cd /data/DaHua_CGI && /home/rzpt/.conda/envs/hermes/bin/python3 -m pytest src/tests/test_full_app.py -v`
- 全量测试：`cd /data/DaHua_CGI && /home/rzpt/.conda/envs/hermes/bin/python3 -m pytest src/tests/ -v`
- 测试用：322/322 ✅

## 输出要求
1. 修改 `src/full_app.py`
2. 更新 `src/tests/test_full_app.py`
3. 更新 `CHANGELOG.md`（新增 GUI 升级条目）
4. 保证测试全部通过后，向 DaHua_CGI 群 @Hermes 报告完成
