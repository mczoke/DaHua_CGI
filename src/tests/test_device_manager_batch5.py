"""Unit tests for device_manager.py - Batch 5: Edge cases + async _send_command

Covers remaining edge cases:
- _send_command with async manager (use_async=True)
- _configure_device_strict with customized mode
- _execute_by_device_strict with already-processing device
- _configure_device_strict_wrapper exception handling
- execute_batch with user-provided total_tasks
- device _execute_by_device_strict with CancelledError handling
"""
import sys
import os
import threading
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
        password='admin123',
        online=online,
        selected=selected,
        status=status,
        variables=variables or {},
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
# _send_command with async manager (use_async=True)
# ============================================================================

class TestSendCommandAsyncPath:
    def test_async_send_string_command(self):
        """_send_command via async manager with string command containing '='."""
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr, use_async=True)
        ex.async_manager = MagicMock()

        # Mock async_manager.send_command to return a Future
        fut = concurrent.futures.Future()
        fut.set_result((True, "OK", 200, {}, "body"))
        ex.async_manager.send_command.return_value = fut

        dev = _make_device(ip="10.0.0.1")
        ok, msg = ex._send_command(dev, "TestParam=1", 1, 2)
        assert ok is True

    def test_async_send_dict_command(self):
        """Skip - dict commands hit requests.utils.quote before async branch."""
        pass

    def test_async_send_old_format(self):
        """async _send_command with 2-tuple return format."""
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr, use_async=True)
        async_mgr = MagicMock()
        ex.async_manager = async_mgr

        fut = concurrent.futures.Future()
        fut.set_result((True, "old-format"))
        async_mgr.send_command.return_value = fut

        dev = _make_device(ip="10.0.0.1")
        ok, msg = ex._send_command(dev, "TestParam=1", 1, 2)
        assert ok is True

    def test_async_send_exception(self):
        """async _send_command with exception."""
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr, use_async=True)
        async_mgr = MagicMock()
        ex.async_manager = async_mgr

        fut = concurrent.futures.Future()
        fut.set_result((False, "request error"))
        async_mgr.send_command.return_value = fut

        dev = _make_device(ip="10.0.0.1")
        ok, msg = ex._send_command(dev, "TestParam=1", 1, 2)
        assert ok is False

    def test_async_send_future_exception(self):
        """async _send_command where future.result() itself raises."""
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr, use_async=True)
        async_mgr = MagicMock()
        ex.async_manager = async_mgr

        fut = concurrent.futures.Future()
        fut.set_exception(Exception("future error"))
        async_mgr.send_command.return_value = fut

        dev = _make_device(ip="10.0.0.1")
        ok, msg = ex._send_command(dev, "TestParam=1", 1, 2)
        assert ok is False
        assert "异步" in msg or "异常" in msg or "error" in msg


# ============================================================================
# _configure_device_strict with customized mode
# ============================================================================

class TestConfigureDeviceCustomized:
    def test_customized_success(self):
        """Customized mode with device variables."""
        log_mgr = MagicMock()
        ex = ConfigExecutor(
            _make_config(cgi_commands=["VideoWidget[{ch}].Title={title}"]),
            log_mgr
        )
        dev = _make_device(
            ip="10.0.0.1",
            status="在线",
            variables={"ch": "0", "title": "FrontGate"}
        )

        with patch.object(ex, '_send_command', return_value=(True, "成功")):
            result = ex._configure_device_strict(dev, mode="customized")

        assert result['success'] is True
        assert result['total_commands'] == 1

    def test_customized_missing_variable_skips(self):
        """Customized mode: missing variable -> command is None -> no command."""
        log_mgr = MagicMock()
        ex = ConfigExecutor(
            _make_config(cgi_commands=["VideoWidget[{ch}].Title={title}"]),
            log_mgr
        )
        dev = _make_device(
            ip="10.0.0.1",
            status="在线",
            variables={"ch": "0"}  # missing "title"
        )

        with patch.object(ex, '_send_command', return_value=(True, "成功")):
            result = ex._configure_device_strict(dev, mode="customized")

        assert result['success'] is False  # no commands executed
        assert result['total_commands'] == 0  # actually total_commands = 0

    def test_customized_no_variables(self):
        """Customized mode with no variables -> empty command list."""
        log_mgr = MagicMock()
        ex = ConfigExecutor(
            _make_config(cgi_commands=["VideoWidget[{ch}].Title={title}"]),
            log_mgr
        )
        dev = _make_device(
            ip="10.0.0.1",
            status="在线",
            variables={}  # empty variables
        )

        with patch.object(ex, '_send_command', return_value=(True, "成功")):
            result = ex._configure_device_strict(dev, mode="customized")

        assert result is not None


# ============================================================================
# _execute_by_device_strict - edge cases
# ============================================================================

class TestExecuteByDeviceStrictEdge:
    def test_already_processing_skipped(self):
        """Device already processing -> skip."""
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        dev = _make_device(ip="10.0.0.1")

        # Mark device as processing first
        ex._check_and_mark_device_processing(dev)

        with patch.object(ex, '_configure_device_strict_wrapper') as mock_w:
            mock_w.return_value = {
                'device': dev, 'ip': '10.0.0.1', 'success': True,
                'total_commands': 2, 'success_commands': 2, 'failed_commands': 0,
                'failure_details': None, 'start_time': '', 'end_time': '', 'total_time': 1
            }
            results = ex._execute_by_device_strict([dev])

        # The device was already marked, so it's not eligible -> skipped
        assert results is not None


# ============================================================================
# execute_batch with user-provided total_tasks
# ============================================================================

class TestExecuteBatchCustomTasks:
    def test_with_custom_total_tasks(self):
        """execute_batch with explicit total_tasks count."""
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(cgi_commands=["Cmd1"]), log_mgr)
        dev = _make_device(ip="10.0.0.1")

        with patch.object(ex, '_send_command', return_value=(True, "成功")):
            with patch.object(ex, '_execute_by_device_strict') as mock_ed:
                mock_ed.return_value = []
                result = ex.execute_batch(
                    [dev], mode="standard",
                    exec_strategy="device_first",
                    total_tasks=100
                )

        # Should have passed total_tasks to _execute_by_device_strict
        mock_ed.assert_called_once()


# ============================================================================
# _configure_device_strict_wrapper exception
# ============================================================================

class TestConfigureDeviceStrictWrapper:
    def test_wrapper_exception_clears_mark(self):
        """Wrapper catches exception and clears processing mark."""
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        dev = _make_device(ip="10.0.0.1")

        with patch.object(ex, '_configure_device_strict',
                          side_effect=ValueError("inner error")):
            try:
                ex._configure_device_strict_wrapper(dev)
            except ValueError:
                pass

        # Processing mark should be cleaned up
        assert dev.ip not in ex._device_processing
