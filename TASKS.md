# 任务列表

## 待办
- (已启动，见进行中)

## 进行中
- [x] Task6 - API 文档 + 集成测试 ✅
  - Claw-Claude → API 文档（6 文件，1361 行，覆盖 5 模块 ✅）
  - OpenClaw → 集成测试（test_full_pipeline_integration.py 19/19 ✅）
- [x] **Task7 - 性能优化** ✅
  - **分项A：async_executor 连接池调优** → Claw-Claude ✅ b2cb2c6
  - **分项B：device_manager 批量设备扫描加速** → Claw-CodeX ✅ e41a366
- [ ] **Task8 - CGI 命令扩展：配置列表方式**（Claw-Claude ▶️ 已分派）
  - config.yaml 添加 `cgi_commands` 配置段（命令名、URL、参数、超时、认证）
  - cgi_reference_manager.py 从 config.yaml 读取命令定义（不再硬编码）
  - 新增 config_only 测试用例验证配置加载

## 待办
- [ ] **Task8 - CGI 命令扩展**
  - 添加告警、智能分析等更多大华 CGI 命令
- [ ] **Task9 - 多设备并发**
  - 批量设备并行 CGI 请求 + 聚合结果

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
