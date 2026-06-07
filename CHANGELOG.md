# 变更日志

## [V9.6-alpha] - 2026-06-07
### GUI 升级 — 聚合报表 Tab + 导出报表 (Claw-Claude ✅)
- 标题版本号 V9.5 → V9.6-alpha
- 新增 `AggregateReportTab`：聚合报表展示 Tab（成功/失败数、按命令统计、按设备统计）
- 新增\"导出报表\"按钮（CSV/Excel/TXT），调用 `AggregateResultCollector`
- 配置执行完成后自动生成聚合报表，展示在\"聚合报表\" Tab
- 更新测试：test_full_app.py 33 → 40 ✅（+7）

### Web UI 构建 (Claw-CodeX ✅)
- 新建 `src/web/` 目录：Flask 应用（566 行）
- 路由：设备管理 / 配置执行 / 聚合报表 / 日志查看 / 配置管理
- 前端：Bootstrap 5 + JS Fetch API（5 个模板 + app.js + style.css）
- 后台全链路复用 `src/utils/` 模块（ConfigManager/DeviceDetector/ConfigExecutor/AggregateResultCollector）
- 启动：`python src/web/app.py`

## [V9.6-alpha] - 2026-06-05 (更新)
### Task9 - 多设备并发 + 聚合报表 (Claw-Claude ✅)
#### 分项A：聚合结果管理器
- 新增 `src/utils/aggregate_collector.py`（267 行）
- `AggregateResultCollector`：跨设备结果合并、按命令/设备维度统计
- 输出：`to_dict()`（JSON 序列化）+ `to_summary_text()`（日志摘要）
- 数据结构：`AggregateReport` / `DeviceResultSummary` / `CommandSummary`

#### 分项B：命令优先策略全并发加速
- `_async_execute_by_command` 重构为 V2：所有设备×命令一次性 `asyncio.gather`
- 通过 `asyncio.Semaphore(config_concurrent)` 控制总并发度
- 保留 stop_callback / progress_callback / 变量过滤 / 设备资格检查

#### 测试
- 新增 `test_multi_device_async.py`：15 个测试用例（481 行）
- 覆盖：聚合报表完整流程、并发限制、停止、变量过滤、空场景
- 全量测试：322/322 ✅（+15）

### 修复：test_full_app.py 30个遗留失败 → 全部通过
- `_RealishFrame` 增强：添加 `__getattr__` 自动 Mock 机制，支持 heading/column/title/geometry/cget 等
- `messagebox`/`filedialog` 直接 Mock，使 assert_called 断言可用
- 修复 `full_app.py`：`load_default_config()` → `get_default_config()`（不存在的方法）
- ScrolledText 改用 `_RealishFrame` 避免 MagicMock.get() 返回非字符串
- 测试结果：33/33 ✅，全量 307/307 ✅

## [V9.6-alpha] - 2026-06-03
### Task6a - API 文档 (Claw-Claude)
- 新增 `docs/api/` 目录，含 6 份文档（1361 行）
- 覆盖 async_executor, config_manager, cgi_reference_manager, device_manager, log_manager
- 含模块索引、依赖图、快速入门、各模块接口说明

### Task6b - 集成测试 (OpenClaw)
- 新增 `test_full_pipeline_integration.py`，19 个测试用例（511 行）
- 覆盖 CGI 请求 → 设备管理 → 日志记录全链路
- 包括异常路径：参数缺失、设备离线、网络错误

### 测试状态
- 全部测试通过：257/257 ✅
- 总覆盖率：83% → 84%

## [V9.6-alpha] - 2026-06-01
### 配置管理重构 (Task1 - Claw-CodeX)
- 新建 `src/config/config.yaml` 作为主配置源（双源加载: yaml优先, 环境变量覆盖）
- `ConfigManager` 重构，兼容旧 json 配置
- `CGIReferenceManager` 完善参数库默认值
- 消除所有硬编码 IP/密码

### 异步执行器优化 (Task2 - Claw-Claude)
- `SyncRequestsExecutor` 添加重试机制 (Retry total=3, backoff_factor=0.5)
- `AsyncExecutor`/`AsyncIOManager` 添加固定 `ThreadPoolExecutor(max_workers=50)`
- `verify_ssl` 默认改为 True，通过配置控制
- 清理重复 executor 文件

### 异常处理&日志优化 (Task3 - Claw-CodeX)
- `log_manager.py` 添加日志级别控制 + 文件轮转
- `log_raw_response` 截断 >1KB
- 消除所有 `except: pass`，替换为错误记录
- 全部 `print()` 替换为 logging

### 全模块代码清理 (Task4 - Claw-Claude)
- `device_manager.py` ConfigExecutor 去重合并精简
- 核心 4 模块添加完整类型注解
- 清理调试脚本 (`debug_*.py`, `diagnose_*.py`)
- 创建 Linux 兼容 `run_tests.sh`

### 环境修复 (Hermes)
- venv 修复：安装 pytest/requests/pandas 等依赖
- 代理下载 numpy 2.4.6 + pandas 3.0.3
- 测试验证：2/2 pytest 通过

## [V9.5] - 2026-05-22
- 项目初始化迁移
- 创建虚拟环境
- 提取依赖
- 初始化 Git 仓库
