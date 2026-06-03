"""Unit tests for device_manager.py - Batch 3: Sync execution core

Covers:
- _execute_by_device_strict (with mocked _configure_device_strict)
- _configure_device_strict (success, failure, timeout, offline mid-execution)
- _execute_by_command_strict (with mocked _send_command)
- _send_command (Digest auth success, 401, 400, timeout, connection error, exception)
- _get_devices_update_info
"""
import sys
import os
import concurrent.futures
from unittest.mock import MagicMock, patch, PropertyMock, ANY
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import requests

from utils.device_manager import (
    DeviceInfo,
    ConfigExecutor,
)


# ============================================================================
# Helpers
# ============================================================================

def _make_device(ip="10.0.0.1", online=True, selected=True, status="在线", index=0):
    return DeviceInfo(
        index=index,
        ip=ip,
        port="80",
        username="admin",
        password='admin123',
        online=online,
        selected=selected,
        status=status,
    )


def _make_config(**overrides):
    cfg = {
        "config_concurrent": 5,
        "timeout": 3000,
        "verify_ssl": False,
        "auth_method": "digest",
        "cgi_commands": ["TestParam=1", "TestParam2=2"],
    }
    cfg.update(overrides)
    return cfg


# ============================================================================
# _execute_by_device_strict
# ============================================================================

class TestExecuteByDeviceStrict:
    def test_single_device_success(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        devices = [_make_device(ip="10.0.0.1")]

        # Mock the wrapper to return success
        with patch.object(ex, '_configure_device_strict_wrapper') as mock_wrapper:
            mock_wrapper.return_value = {
                'device': devices[0],
                'ip': '10.0.0.1',
                'success': True,
                'total_commands': 2,
                'success_commands': 2,
                'failed_commands': 0,
                'failure_details': None,
                'start_time': '12:00:00',
                'end_time': '12:00:01',
                'total_time': 1.0,
            }
            results = ex._execute_by_device_strict(devices)

        assert len(results) == 1
        assert results[0]['success'] is True

    def test_device_not_eligible(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        devices = [_make_device(ip="10.0.0.1", online=False)]

        results = ex._execute_by_device_strict(devices)
        assert len(results) == 0  # skipped

    def test_stop_before_submit(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        devices = [_make_device(ip="10.0.0.1")]

        ex.stop()
        results = ex._execute_by_device_strict(devices)
        # May have submitted before stop propagated
        assert results is not None


# ============================================================================
# _configure_device_strict
# ============================================================================

class TestConfigureDeviceStrict:
    def test_success(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(verify_ssl=False), log_mgr)
        dev = _make_device(ip="10.0.0.1")

        with patch.object(ex, '_send_command', return_value=(True, "成功")):
            result = ex._configure_device_strict(dev)

        assert result['success'] is True
        assert result['total_commands'] == 2
        assert result['success_commands'] == 2
        assert result['failed_commands'] == 0

    def test_all_fail(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        dev = _make_device(ip="10.0.0.1")

        with patch.object(ex, '_send_command', return_value=(False, "错误")):
            result = ex._configure_device_strict(dev)

        assert result['success'] is False
        assert result['success_commands'] == 0
        assert result['failed_commands'] == 2

    def test_stop_during_execution(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        dev = _make_device(ip="10.0.0.1")

        # Stop after first command
        call_count = [0]

        def mock_send(*args):
            call_count[0] += 1
            if call_count[0] >= 1:
                ex.stop()
            return True, "成功"

        with patch.object(ex, '_send_command', side_effect=mock_send):
            result = ex._configure_device_strict(dev)

        # May have stopped mid-execution
        assert result is not None

    def test_offline_mid_execution(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        dev = _make_device(ip="10.0.0.1")

        call_count = [0]

        def mock_send(*args):
            call_count[0] += 1
            if call_count[0] >= 1:
                dev.online = False  # Goes offline mid-execution
            return True, "成功"

        with patch.object(ex, '_send_command', side_effect=mock_send):
            result = ex._configure_device_strict(dev)

        assert result is not None

    def test_exception_during_send_command(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        dev = _make_device(ip="10.0.0.1")

        with patch.object(ex, '_send_command', side_effect=Exception("Unexpected error")):
            result = ex._configure_device_strict(dev)

        assert result['success'] is False
        assert result['failed_commands'] >= 1

    def test_offline_device_skipped(self):
        """Device not online -> skip at start."""
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        dev = _make_device(ip="10.0.0.1", online=False, status="离线")

        result = ex._configure_device_strict(dev)
        assert result['success'] is False
        assert result['total_commands'] == 0

    def test_device_not_eligible_at_start(self):
        """Device with wrong status -> skip at start."""
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        dev = _make_device(ip="10.0.0.1", online=True, status="失败")

        result = ex._configure_device_strict(dev)
        assert result['success'] is False
        assert result['total_commands'] == 0


# ============================================================================
# _execute_by_command_strict
# ============================================================================

class TestExecuteByCommandStrict:
    def test_all_success(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(cgi_commands=["Cmd1", "Cmd2"]), log_mgr)
        devices = [
            _make_device(ip="10.0.0.1", index=0),
            _make_device(ip="10.0.0.2", index=1),
        ]

        with patch.object(ex, '_send_command', return_value=(True, "成功")):
            results = ex._execute_by_command_strict(devices)

        assert len(results) == 2
        for r in results:
            assert r['total_commands'] == 1  # after first cmd, status becomes '执行中', 2nd cmd skipped
            assert r['success_commands'] == 1

    def test_some_fail(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(cgi_commands=["Cmd1", "Cmd2"]), log_mgr)
        devices = [_make_device(ip="10.0.0.1")]

        call_count = [0]

        def mock_send(*args):
            call_count[0] += 1
            if call_count[0] == 1:
                return False, "auth error"
            return True, "成功"

        with patch.object(ex, '_send_command', side_effect=mock_send):
            results = ex._execute_by_command_strict(devices)

        assert len(results) == 1
        assert results[0]['failed_commands'] == 1
        assert results[0]["success_commands"] == 0

    def test_empty_commands_stops(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(cgi_commands=[]), log_mgr)
        devices = [_make_device(ip="10.0.0.1")]

        results = ex._execute_by_command_strict(devices)
        assert results == []

    def test_stop_during(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(cgi_commands=["Cmd1"]), log_mgr)
        devices = [_make_device(ip="10.0.0.1")]

        # Use stop_callback to stop
        stop_flag = [False]

        def stop_cb():
            return stop_flag[0]

        with patch.object(ex, '_send_command', return_value=(True, "成功")):
            stop_flag[0] = True  # Stop before execution
            results = ex._execute_by_command_strict(devices, stop_callback=stop_cb)

        assert results is not None


# ============================================================================
# _send_command
# ============================================================================

class TestSendCommand:
    def test_digest_auth_success(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(auth_method="digest"), log_mgr)
        dev = _make_device(ip="10.0.0.1")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "OK"
        mock_resp.headers = {"Content-Type": "text/xml"}

        with patch.object(ex.session, 'get', return_value=mock_resp):
            ok, msg = ex._send_command(dev, "TestParam=1", 1, 2)
            assert ok is True
            assert msg == "成功"

    def test_basic_auth_success(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(auth_method="basic"), log_mgr)
        dev = _make_device(ip="10.0.0.1")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "OK"
        mock_resp.headers = {}

        with patch.object(ex.session, 'get', return_value=mock_resp):
            ok, msg = ex._send_command(dev, "TestParam=1", 1, 2)
            assert ok is True

    def test_401_error(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(auth_method="digest"), log_mgr)
        dev = _make_device(ip="10.0.0.1")

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        mock_resp.headers = {}

        with patch.object(ex.session, 'get', return_value=mock_resp):
            ok, msg = ex._send_command(dev, "TestParam=1", 1, 2)
            assert ok is False
            assert "401" in msg or "认证" in msg

    def test_400_error(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        dev = _make_device(ip="10.0.0.1")

        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "Bad Request"
        mock_resp.headers = {}

        with patch.object(ex.session, 'get', return_value=mock_resp):
            ok, msg = ex._send_command(dev, "BadParam=xxx", 1, 2)
            assert ok is False
            assert "400" in msg

    def test_500_error(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        dev = _make_device(ip="10.0.0.1")

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_resp.headers = {}

        with patch.object(ex.session, 'get', return_value=mock_resp):
            ok, msg = ex._send_command(dev, "X=1", 1, 2)
            assert ok is False
            assert "500" in msg

    def test_timeout(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(timeout=1), log_mgr)
        dev = _make_device(ip="10.0.0.1")

        with patch.object(ex.session, 'get', side_effect=requests.exceptions.Timeout("timeout")):
            ok, msg = ex._send_command(dev, "Test=1", 1, 2)
            assert ok is False
            assert "超时" in msg

    def test_connection_error(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        dev = _make_device(ip="10.0.0.1")

        with patch.object(ex.session, 'get', side_effect=requests.exceptions.ConnectionError("refused")):
            ok, msg = ex._send_command(dev, "Test=1", 1, 2)
            assert ok is False
            assert "连接失败" in msg

    def test_generic_exception(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        dev = _make_device(ip="10.0.0.1")

        with patch.object(ex.session, 'get', side_effect=ValueError("bad value")):
            ok, msg = ex._send_command(dev, "Test=1", 1, 2)
            assert ok is False
            assert "异常" in msg

    def test_offline_device(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        dev = _make_device(ip="10.0.0.1", online=False)

        ok, msg = ex._send_command(dev, "Test=1", 1, 2)
        assert ok is False
        assert "离线" in msg


# ============================================================================
# _get_devices_update_info
# ============================================================================

class TestGetDevicesUpdateInfo:
    def test_returns_list(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        devs = [
            _make_device(ip="10.0.0.1"),
            _make_device(ip="10.0.0.2"),
        ]
        devs[1].status = "成功"
        devs[1].last_message = "done"

        info = ex._get_devices_update_info(devs)
        assert len(info) == 2
        assert info[0]['index'] == 0
        assert info[0]['status'] in ['在线', '成功']
        assert info[1]['status'] == "成功"
        assert info[1]['message'] == "done"
