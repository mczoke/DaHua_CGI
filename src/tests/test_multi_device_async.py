"""
集成测试 — 多设备并发 + 聚合报表

覆盖：
  1. AggregateReport 基础功能（mock 3设备×3命令）
  2. 部分失败场景
  3. 空场景
  4. _async_execute_by_command 全并发
  5. 中途停止
  6. 部分命令失败
  7. 完整流程（mock 5 设备并发）
"""
import sys
import os
import asyncio
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock, ANY
from typing import List, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from utils.device_manager import (
    DeviceInfo,
    ConfigExecutor,
)
from utils.aggregate_collector import (
    AggregateResultCollector,
    AggregateReport,
    DeviceResultSummary,
    CommandSummary,
)
from utils.async_executor import AsyncIOManager


# ============================================================================
# Helpers
# ============================================================================

def _make_device(ip="10.0.0.1", online=True, selected=True, status="在线", index=0, variables=None):
    return DeviceInfo(
        index=index,
        ip=ip,
        port="80",
        username="admin",
        password="admin123",
        online=online,
        selected=selected,
        status=status,
        variables=variables or {},
    )


def _make_config(**overrides):
    cfg = {
        "config_concurrent": 80,
        "timeout": 3000,
        "verify_ssl": False,
        "auth_method": "digest",
        "cgi_commands": ["TestParam=1", "TestParam2=2", "TestParam3=3"],
    }
    cfg.update(overrides)
    return cfg


def _mock_send_result(ok: bool, msg: str = "OK"):
    """模拟 AsyncIOManager.send_command_async 的返回值"""
    fut = asyncio.Future()
    fut.set_result((ok, msg, 200 if ok else 500, {}, msg))
    return fut


# ============================================================================
# 分项 A 测试 — AggregateResultCollector
# ============================================================================

class TestAggregateReport:
    """AggregateReport 基础功能"""

    def test_basic_collect(self):
        """标准 3设备×3命令 全部成功场景"""
        devices = [
            _make_device(ip="10.0.0.1", index=0),
            _make_device(ip="10.0.0.2", index=1),
            _make_device(ip="10.0.0.3", index=2),
        ]
        results = [
            {"ip": "10.0.0.1", "port": "80", "success": True, "total_commands": 3,
             "success_commands": 3, "failed_commands": 0, "total_time": 1.5, "failure_details": ""},
            {"ip": "10.0.0.2", "port": "80", "success": True, "total_commands": 3,
             "success_commands": 3, "failed_commands": 0, "total_time": 2.0, "failure_details": ""},
            {"ip": "10.0.0.3", "port": "80", "success": True, "total_commands": 3,
             "success_commands": 3, "failed_commands": 0, "total_time": 1.8, "failure_details": ""},
        ]

        start = datetime.now()
        report = AggregateResultCollector.collect(results, devices, start)

        assert report.total_devices == 3
        assert report.online_devices == 3
        assert report.skipped_devices == 0
        assert report.success_count == 9
        assert report.failed_count == 0
        assert report.success_rate == 100.0
        assert len(report.per_device) == 3
        assert len(report.failure_details) == 0

    def test_collect_with_failures(self):
        """部分设备部分命令失败"""
        devices = [
            _make_device(ip="10.0.0.1", index=0),
            _make_device(ip="10.0.0.2", index=1),
            _make_device(ip="10.0.0.3", index=2),
        ]
        results = [
            {"ip": "10.0.0.1", "port": "80", "success": True, "total_commands": 3,
             "success_commands": 3, "failed_commands": 0, "total_time": 1.5, "failure_details": ""},
            {"ip": "10.0.0.2", "port": "80", "success": False, "total_commands": 3,
             "success_commands": 1, "failed_commands": 2, "total_time": 3.0,
             "failure_details": "命令1: Timeout; 命令2: AuthError"},
            {"ip": "10.0.0.3", "port": "80", "success": False, "total_commands": 3,
             "success_commands": 0, "failed_commands": 3, "total_time": 5.0,
             "failure_details": "所有命令失败"},
        ]

        report = AggregateResultCollector.collect(results, devices)

        assert report.total_devices == 3
        assert report.success_count == 4
        assert report.failed_count == 5
        assert report.success_rate == pytest.approx(44.44, rel=0.01)
        assert len(report.failure_details) == 2

    def test_collect_empty(self):
        """无设备 / 无命令场景"""
        # 空设备
        report = AggregateResultCollector.collect([], [])
        assert report.total_devices == 0
        assert report.online_devices == 0
        assert report.success_rate == 0.0
        assert len(report.per_device) == 0
        assert len(report.failure_details) == 0

        # 有设备但无结果
        devices = [_make_device(ip="10.0.0.1", index=0)]
        report = AggregateResultCollector.collect([], devices)
        assert report.total_devices == 1
        assert report.online_devices == 1
        assert report.total_commands == 0

    def test_to_dict(self):
        """验证 to_dict 可序列化"""
        devices = [_make_device(ip="10.0.0.1")]
        results = [{"ip": "10.0.0.1", "port": "80", "success": True, "total_commands": 2,
                    "success_commands": 2, "failed_commands": 0, "total_time": 0.5, "failure_details": ""}]
        report = AggregateResultCollector.collect(results, devices)
        d = AggregateResultCollector.to_dict(report)
        assert "总览" in d
        assert "设备维度" in d
        assert "命令维度" in d
        assert "失败详情" in d
        assert d["总览"]["总设备数"] == 1
        assert len(d["设备维度"]) == 1

    def test_to_summary_text(self):
        """验证 to_summary_text 输出格式"""
        devices = [_make_device(ip="10.0.0.1"), _make_device(ip="10.0.0.2")]
        results = [
            {"ip": "10.0.0.1", "port": "80", "success": True, "total_commands": 2,
             "success_commands": 2, "failed_commands": 0, "total_time": 0.5, "failure_details": ""},
            {"ip": "10.0.0.2", "port": "80", "success": False, "total_commands": 2,
             "success_commands": 0, "failed_commands": 2, "total_time": 1.0,
             "failure_details": "命令1: Error"},
        ]
        report = AggregateResultCollector.collect(results, devices)
        text = AggregateResultCollector.to_summary_text(report)
        assert "聚合报表" in text
        assert "2成功" in text
        assert "2失败" in text
        assert "10.0.0.1" in text
        assert "10.0.0.2" in text


# ============================================================================
# 分项 B 测试 — _async_execute_by_command V2 全并发
# ============================================================================

@pytest.mark.asyncio
class TestAsyncExecuteByCommandV2:
    """测试 _async_execute_by_command V2 (全并发)"""

    async def _run_async_command(self, config=None, devices=None, mock_result=None, mode="standard"):
        """辅助：创建 ConfigExecutor 并执行 async command"""
        cfg = _make_config(**(config or {}))
        log_mgr = MagicMock()
        ex = ConfigExecutor(cfg, log_mgr, use_async=True)
        ex.async_manager = MagicMock(spec=AsyncIOManager)

        async def mock_send_async(device, command, use_url_auth=False):
            return (True, "OK", 200, {}, "OK")

        ex.async_manager.send_command_async = MagicMock(side_effect=mock_send_async)

        result = await ex._async_execute_by_command(
            devices or [],
            mode=mode,
            progress_callback=None,
            stop_callback=None,
        )
        return result, ex

    async def test_basic_concurrent_execution(self):
        """基本并发执行：3设备×3命令全部成功"""
        devices = [
            _make_device(ip="10.0.0.1", index=0),
            _make_device(ip="10.0.0.2", index=1),
            _make_device(ip="10.0.0.3", index=2),
        ]
        results, ex = await self._run_async_command(devices=devices)

        assert len(results) == 3
        for r in results:
            assert r["total_commands"] == 3
            assert r["success_commands"] == 3
            assert r["failed_commands"] == 0
            assert r["success"] is True

    async def test_partial_failure(self):
        """部分命令失败场景 — 按设备 IP 路由 mock 结果"""
        devices = [
            _make_device(ip="10.0.0.1", index=0),
            _make_device(ip="10.0.0.2", index=1),
        ]

        # 按 device.ip 路由不同的 mock 行为
        call_counts = {}
        device_results = {
            "10.0.0.1": [(True, "OK"), (True, "OK"), (True, "OK")],
            "10.0.0.2": [(False, "错误1"), (False, "错误2"), (True, "OK")],
        }

        cfg = _make_config()
        log_mgr = MagicMock()
        ex = ConfigExecutor(cfg, log_mgr, use_async=True)
        ex.async_manager = MagicMock(spec=AsyncIOManager)

        async def mock_send_async(device, command, use_url_auth=False):
            ip = device.ip
            if ip not in call_counts:
                call_counts[ip] = 0
            idx = call_counts[ip]
            call_counts[ip] = idx + 1
            results_list = device_results.get(ip, [(True, "OK")])
            ok, msg = results_list[idx] if idx < len(results_list) else (True, "OK")
            return (ok, msg, 200 if ok else 500, {}, msg)

        ex.async_manager.send_command_async = MagicMock(side_effect=mock_send_async)

        result = await ex._async_execute_by_command(
            devices,
            mode="standard",
            progress_callback=None,
            stop_callback=None,
        )

        assert len(result) == 2
        # 按 IP 找结果（不依赖顺序）
        res1 = next(r for r in result if r["ip"] == "10.0.0.1")
        res2 = next(r for r in result if r["ip"] == "10.0.0.2")

        assert res1["success_commands"] == 3
        assert res1["failed_commands"] == 0
        assert res1["success"] is True

        assert res2["success_commands"] == 1
        assert res2["failed_commands"] == 2
        assert res2["success"] is True  # 原有逻辑：至少有一条成功即为 True
        assert "错误1" in res2["failure_details"]
        assert "错误2" in res2["failure_details"]

    async def test_stop_callback(self):
        """中途停止回调"""
        devices = [
            _make_device(ip="10.0.0.1", index=0),
            _make_device(ip="10.0.0.2", index=1),
        ]
        cfg = _make_config(config_concurrent=80)
        log_mgr = MagicMock()
        ex = ConfigExecutor(cfg, log_mgr, use_async=True)
        ex.async_manager = MagicMock(spec=AsyncIOManager)

        call_count = 0

        async def mock_send_async(device, command, use_url_auth=False):
            nonlocal call_count
            call_count += 1
            return (True, "OK", 200, {}, "OK")

        ex.async_manager.send_command_async = MagicMock(side_effect=mock_send_async)

        # 在第一次调用后立即触发停止
        stop_counter = 0

        def stop_after_first():
            nonlocal stop_counter
            stop_counter += 1
            return stop_counter > 1

        result = await ex._async_execute_by_command(
            devices,
            mode="standard",
            progress_callback=None,
            stop_callback=stop_after_first,
        )
        # 因为有2设备×3命令=6任务，stop_callback在 >1 次后返回 True
        # 实际上 stop_callback 在每个任务内部检查，返回时会在任务内部执行 return "已停止"
        # 所以至少有 1 个任务正常完成，5 个返回"已停止"（每个独立任务内部检查）
        # 但具体数值取决于并发执行顺序
        assert len(result) == 2

    async def test_concurrent_control(self):
        """验证并发度受 config_concurrent 限制"""
        devices = [_make_device(ip=f"10.0.0.{i}", index=i) for i in range(5)]
        cfg = _make_config(config_concurrent=2)  # 限制并发度为 2
        log_mgr = MagicMock()
        ex = ConfigExecutor(cfg, log_mgr, use_async=True)
        ex.async_manager = MagicMock(spec=AsyncIOManager)

        concurrent_count = 0
        peak_concurrent = 0

        async def mock_send_async(device, command, use_url_auth=False):
            nonlocal concurrent_count, peak_concurrent
            concurrent_count += 1
            peak_concurrent = max(peak_concurrent, concurrent_count)
            # yield control to allow others to start
            await asyncio.sleep(0.001)
            concurrent_count -= 1
            return (True, "OK", 200, {}, "OK")

        ex.async_manager.send_command_async = MagicMock(side_effect=mock_send_async)

        result = await ex._async_execute_by_command(
            devices,
            mode="standard",
            progress_callback=None,
            stop_callback=None,
        )
        # config_concurrent=2，峰值并发应该 <= 2
        assert peak_concurrent <= 2, f"峰值并发 {peak_concurrent} > 2"
        assert len(result) == 5

    async def test_customized_mode_variable_filtering(self):
        """customized 模式的变量过滤"""
        devices = [
            _make_device(ip="10.0.0.1", index=0, variables={"DeviceName": "Gate1"}),
            _make_device(ip="10.0.0.2", index=1, variables={"DeviceName": "Gate2"}),
        ]
        cfg = _make_config(cgi_commands=["TestParam={DeviceName}", "StaticParam=1"])
        log_mgr = MagicMock()
        ex = ConfigExecutor(cfg, log_mgr, use_async=True)
        ex.async_manager = MagicMock(spec=AsyncIOManager)

        sent_commands = []

        async def mock_send_async(device, command, use_url_auth=False):
            sent_commands.append((device.ip, command))
            return (True, "OK", 200, {}, "OK")

        ex.async_manager.send_command_async = MagicMock(side_effect=mock_send_async)

        with patch.object(ex, "_generate_custom_command",
                          side_effect=lambda cmd, vars: cmd.replace("{DeviceName}", vars.get("DeviceName", ""))):
            result = await ex._async_execute_by_command(
                devices,
                mode="customized",
                progress_callback=None,
                stop_callback=None,
            )

        assert len(result) == 2
        assert len(sent_commands) == 2 * 2  # 2 devices × 2 commands
        # 验证变量替换生效
        var_commands = [(ip, cmd) for ip, cmd in sent_commands if "Gate" in cmd]
        assert len(var_commands) == 2

    async def test_no_online_devices(self):
        """无在线设备场景"""
        devices = [_make_device(ip="10.0.0.1", online=False)]
        results, ex = await self._run_async_command(devices=devices)
        assert results == []

    async def test_empty_commands(self):
        """无命令配置场景"""
        devices = [_make_device(ip="10.0.0.1")]
        results, ex = await self._run_async_command(
            devices=devices,
            config={"cgi_commands": []},
        )
        assert results == []

    async def test_device_eligible_filtering(self):
        """_is_device_eligible_for_config 过滤"""
        devices = [_make_device(ip="10.0.0.1", index=0)]
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr, use_async=True)
        ex.async_manager = MagicMock(spec=AsyncIOManager)

        async def mock_send(device, command, use_url_auth=False):
            return (True, "OK", 200, {}, "OK")

        ex.async_manager.send_command_async = MagicMock(side_effect=mock_send)

        with patch.object(ex, "_is_device_eligible_for_config", return_value=False):
            result = await ex._async_execute_by_command(
                devices,
                mode="standard",
                progress_callback=None,
                stop_callback=None,
            )
        # 设备被过滤掉，应该返回空结果列表（但 devices 非空，结果列表为空是为 []）
        # 实际上如果所有设备都被过滤，all_tasks 为空，返回 []
        assert result == []


# ============================================================================
# 聚合报表集成测试
# ============================================================================

class TestAggregateIntegration:
    """聚合报表 + 异步执行集成验证"""

    def test_report_empty_no_crash(self):
        """空场景不崩溃"""
        report = AggregateResultCollector.collect([], [])
        assert isinstance(report, AggregateReport)
        assert report.success_rate == 0.0

    def test_report_with_aggregate_data(self):
        """聚合报表集成"""
        devices = [
            _make_device(ip="10.0.0.1", index=0),
            _make_device(ip="10.0.0.2", index=1),
            _make_device(ip="10.0.0.3", online=False, index=2),
            _make_device(ip="10.0.0.4", index=3),
            _make_device(ip="10.0.0.5", index=4),
        ]
        results = [
            {"ip": "10.0.0.1", "port": "80", "success": True, "total_commands": 3,
             "success_commands": 3, "failed_commands": 0, "total_time": 1.0, "failure_details": ""},
            {"ip": "10.0.0.2", "port": "80", "success": True, "total_commands": 3,
             "success_commands": 3, "failed_commands": 0, "total_time": 1.5, "failure_details": ""},
            {"ip": "10.0.0.4", "port": "80", "success": False, "total_commands": 3,
             "success_commands": 2, "failed_commands": 1, "total_time": 2.0,
             "failure_details": "命令2: Timeout"},
            {"ip": "10.0.0.5", "port": "80", "success": True, "total_commands": 3,
             "success_commands": 3, "failed_commands": 0, "total_time": 1.2, "failure_details": ""},
        ]

        report = AggregateResultCollector.collect(results, devices)

        # 5 个设备, 4 个在线
        assert report.total_devices == 5
        assert report.online_devices == 4
        assert report.skipped_devices == 1  # 10.0.0.3 离线
        assert report.success_count == 11
        assert report.failed_count == 1
        assert report.success_rate == pytest.approx(91.67, rel=0.01)
        assert len(report.per_device) == 4  # 只有在线设备有结果

        # to_summary_text 不崩溃
        text = AggregateResultCollector.to_summary_text(report)
        assert "5总计" in text  # total_devices
        assert "11成功" in text
        assert "1失败" in text

        # to_dict 不崩溃
        data = AggregateResultCollector.to_dict(report)
        assert data["总览"]["总设备数"] == 5
        assert len(data["失败详情"]) == 1
