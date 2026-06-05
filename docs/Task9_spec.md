# Task9 规格说明 - 多设备并发 + 聚合报表

## 分项A：AggregateResultCollector（新增模块或挂载到 device_manager.py）

**文件位置：** `src/utils/aggregate_collector.py`（独立模块，便于测试）

**核心功能：**
跨多设备并发执行完成后的结果汇总，输出结构化报表。

**数据结构：**

```python
@dataclass
class AggregateReport:
    total_devices: int          # 总设备数
    online_devices: int         # 在线设备数
    skipped_devices: int        # 跳过的设备数
    total_commands: int         # 总命令数
    success_count: int          # 成功命令数
    failed_count: int           # 失败命令数
    success_rate: float         # 成功率（百分比）
    total_duration: float       # 总耗时（秒）
    per_device: List[DeviceResultSummary]  # 每台设备摘要
    per_command: Dict[str, CommandSummary]  # 按命令摘要
    failure_details: List[Dict] # 失败详情列表

@dataclass
class DeviceResultSummary:
    ip: str
    port: str
    status: str                 # 在线/离线/成功/部分完成/失败
    total_commands: int
    success: int
    failed: int
    duration: float
    last_message: str

@dataclass
class CommandSummary:
    command_name: str
    total_attempts: int
    success: int
    failed: int
    avg_duration: float
    failure_rate: float
```

**核心方法：**
- `collect(results: List[dict], devices: List[DeviceInfo], start_time: datetime) -> AggregateReport`
- `to_dict(report: AggregateReport) -> dict` — 转换为可序列化 dict
- `to_summary_text(report: AggregateReport) -> str` — 生成易于日志输出的摘要文本

## 分项B：命令优先策略并发加速

**改造目标：** `device_manager.py` 中的 `_async_execute_by_command()` 方法。

**当前问题：**
命令维度上的 `for cmd_idx, base_cmd in enumerate(base_commands)` 每一轮对每个设备串行发请求（受 `asyncio.Semaphore` 限制），
实际是"命令内设备间并发，命令间串行"。

**改造方案：**
将命令优先策略改为**真正的全并发**——所有设备×所有命令一次性提交到 asyncio，通过 `asyncio.Semaphore(config_concurrent)` 控制总并发度：

```python
async def _async_execute_by_command_v2(self, devices, ...):
    semaphore = asyncio.Semaphore(self.config_concurrent)
    
    # 生成所有任务：(dev, cmd_idx, base_cmd)
    all_tasks = []
    for dev in online_devices:
        for cmd_idx, base_cmd in enumerate(base_commands):
            # 检查命令是否适用（变量过滤等）
            ...
            all_tasks.append(asyncio.create_task(
                self._send_single_command(dev, cmd_idx, base_cmd, semaphore)
            ))
    
    # 一次性等待所有
    completed = await asyncio.gather(*all_tasks, return_exceptions=True)
```

**关键注意事项：**
1. 保留原有的 `stop_callback` 检查（应实现为在任务内部检查，而不是在 for 循环间检查）
2. 保留原有的进度回调 `progress_callback`（可以批量汇总后触发）
3. 保留 `_is_device_eligible_for_config` 和变量过滤逻辑
4. 保留 log_manager 记录
5. 保留 `_async_execute_by_device` 不变（原有的设备优先方案已经够好）

## 分项C：集成测试

**文件位置：** `src/tests/test_multi_device_async.py`

**测试用例覆盖：**
1. `test_aggregate_report_basic` — 聚合报表基础功能（mock 3设备×3命令）
2. `test_aggregate_report_with_failures` — 部分设备部分命令失败场景
3. `test_aggregate_report_empty` — 无设备/无命令场景
4. `test_async_execute_by_command_v2_concurrent` — 验证新命令优先策略真正并发了所有任务
5. `test_async_execute_by_command_v2_stop` — 中途停止验证
6. `test_async_execute_by_command_v2_partial_failure` — 部分命令失败场景
7. `test_device_manager_integration_multi_device` — 完整流程（mock 5 设备并发）

**Mock 策略：**
- `AsyncIOManager.send_command_async` 返回 `(ok, msg, 200, {}, None)`
- `DeviceManager.config_concurrent` 设为 80（默认值）
- 使用 `asyncio.get_event_loop().run_until_complete()` 跑协程
- 或用 `pytest-asyncio` 的 `@pytest.mark.asyncio`

## 验收标准
- [ ] 新增模块到位，pytest 全绿
- [ ] 全量测试：307+新增 >= 320 ✅
- [ ] 聚合报表格式可读（设备维度 + 命令维度）
- [ ] 命令优先策略不再命令间串行，实现等量并发
