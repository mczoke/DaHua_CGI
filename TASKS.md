# 任务列表

## 进行中
- [x] **Task9 - 多设备并发 + 聚合报表** ✅
  - **分项A：聚合结果管理器** — 已完成
    - `src/utils/aggregate_collector.py`：AggregateResultCollector + 3个数据类，267行
    - 输出结构化报表（dict + text），支持按设备/命令维度统计
  - **分项B：命令优先策略并发加速** — 已完成
    - `_async_execute_by_command` 改为全并发：所有设备×命令同时 asyncio.gather
    - Semaphore(config_concurrent) 控制并发上限
  - **分项C：集成测试** — 已完成
    - `test_multi_device_async.py`：15个测试覆盖聚合报表/并发执行/部分失败
    - 全量测试 329/329 ✅（GUI 升级新增 7 个）
- [x] **GUI 升级** (Claw-Claude)
  - 版本号 V9.5 → V9.6-alpha
  - 新增聚合报表 Tab + 导出报表按钮
  - test_full_app.py: 33→40 ✅
- [x] **Web UI 构建** (Claw-CodeX)
  - `src/web/`：Flask 应用，566 行
  - 设备管理/配置执行/聚合报表/日志查看
  - 启动：`python src/web/app.py`

## 待办
- [x] GitHub 推送完成 ✅（仓库：mczoke/DaHua_CGI）

## 已完成
- [x] Task1 - 配置管理重构 (Claw-CodeX)
- [x] Task2 - 异步执行器优化 (Claw-Claude)
- [x] Task3 - 异常处理&日志优化 (Claw-CodeX)
- [x] Task4 - 全模块代码清理 (Claw-Claude)
- [x] venv 环境修复 (Hermes)
- [x] test_async_manager.py → pytest 格式 (4 cases)
- [x] test_with_mock_server.py → pytest 格式 (2 cases: digest + basic auth)
- [x] test_stop_behavior.py → pytest 格式 (1 case)
- [x] 全部测试通过: 9/9 ✅
- [x] test_execute_batch_integration.py — 10 个测试覆盖 5 大分支 (Hermes)
- [x] 全部测试通过: 19/19 ✅ | 覆盖率: 38%
- [x] test_async_executor_unit.py — 28 个测试覆盖 async_executor.py 全路径 (Hermes)
- [x] async_executor.py 覆盖率: 59% → 96%（超 80% 目标 ✅）
- [x] 全部测试通过: 47/47 ✅ | 总覆盖率: 46%
- [x] Task5 - 覆盖率提升：cgi_reference_manager 0%→100%, config_manager 0%→96%, log_manager 56%→99% (OpenClaw)
- [x] 总覆盖率：59% → 83%（超 80% 目标 ✅）
- [x] 全部测试通过：238/238 ✅（排除 pre-existing test_full_app.py 30个失败）
- [x] Task6 - API 文档 + 集成测试 ✅
- [x] Task7 - 性能优化 ✅
- [x] Task8 - CGI 命令扩展：告警/智能分析/设备管理 ✅
- [x] 修复 test_full_app.py 30个遗留失败 → 33/33 ✅ | 全量 307/307 ✅
- [x] Task9 - 多设备并发 + 聚合报表 ✅ | 全量 322/322 ✅
