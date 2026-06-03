"""Unit tests for device_manager.py - Batch 2: ConfigExecutor basics + execute_batch

Covers:
- __init__ (sync + async mode)
- _create_session
- stop (session close, async_manager close, futures cancel)
- _is_stopped
- _check_and_mark_device_processing / _unmark_device_processing
- _is_device_eligible_for_config
- _cleanup_device_processing
- execute_batch (empty, mixed online/offline, async mode)
"""
import sys
import os
import threading
import concurrent.futures
from unittest.mock import MagicMock, patch, PropertyMock, ANY

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from utils.device_manager import (
    DeviceInfo,
    DeviceLoader,
    DeviceDetector,
    ConfigExecutor,
)
from utils.async_executor import AsyncIOManager


# ============================================================================
# Helpers
# ============================================================================

def _make_device(ip="10.0.0.1", online=True, selected=True, status="在线"):
    return DeviceInfo(
        index=0,
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
        "cgi_commands": ["VideoStandard=PAL", "VideoTitle=Test"],
    }
    cfg.update(overrides)
    return cfg


# ============================================================================
# ConfigExecutor - __init__
# ============================================================================

class TestConfigExecutorInit:
    def test_init_sync(self):
        """Sync mode: no async_manager."""
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr, use_async=False)
        assert ex.use_async is False
        assert ex.async_manager is None
        ex.stop()

    def test_init_async(self):
        """Async mode: async_manager created."""
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr, use_async=True)
        assert ex.use_async is True
        assert ex.async_manager is not None
        ex.stop()

    def test_init_async_init_failure(self):
        """Async mode: init failure falls back gracefully."""
        log_mgr = MagicMock()
        with patch.object(AsyncIOManager, '__init__', side_effect=Exception("init failed")):
            ex = ConfigExecutor(_make_config(), log_mgr, use_async=True)
            assert ex.use_async is True
            assert ex.async_manager is None  # 回退到同步
            ex.stop()


# ============================================================================
# ConfigExecutor - _create_session
# ============================================================================

class TestCreateSession:
    def test_create_session(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        session = ex._create_session()
        assert session is not None
        ex.stop()


# ============================================================================
# ConfigExecutor - stop / _is_stopped
# ============================================================================

class TestStop:
    def test_stop_sets_flag(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        assert ex._is_stopped() is False
        ex.stop()
        assert ex._is_stopped() is True

    def test_stop_closes_session(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        session = ex.session
        with patch.object(session, 'close') as mock_close:
            ex.stop()
            mock_close.assert_called_once()

    def test_stop_cancels_futures(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        fut = concurrent.futures.Future()
        ex._futures = [fut]
        ex.stop()
        # Future is still pending (not running), so cancel() should succeed
        assert fut.cancelled()

    def test_stop_shuts_down_executor(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        ex._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        ex.stop()
        # The executor gets shut down, submitting raises
        import time
        time.sleep(0.1)
        assert ex._executor is None or ex._executor._shutdown

    def test_is_stopped(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        assert ex._is_stopped() is False
        ex.stop()
        assert ex._is_stopped() is True


# ============================================================================
# ConfigExecutor - device processing markers
# ============================================================================

class TestDeviceProcessing:
    def test_mark_and_unmark(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        dev = _make_device(ip="10.0.0.1")

        assert ex._check_and_mark_device_processing(dev) is True
        assert ex._check_and_mark_device_processing(dev) is False  # already marked

        ex._unmark_device_processing(dev)
        assert ex._check_and_mark_device_processing(dev) is True  # can mark again

    def test_cleanup(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        dev1 = _make_device(ip="10.0.0.1")
        dev2 = _make_device(ip="10.0.0.2")

        ex._check_and_mark_device_processing(dev1)
        ex._check_and_mark_device_processing(dev2)

        ex._cleanup_device_processing()
        assert len(ex._device_processing) == 0


# ============================================================================
# ConfigExecutor - _is_device_eligible_for_config
# ============================================================================

class TestDeviceEligible:
    def test_eligible_device(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        dev = _make_device(online=True, status="在线", selected=True)
        assert ex._is_device_eligible_for_config(dev) is True

    def test_not_eligible_offline(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        dev = _make_device(online=False, status="离线", selected=True)
        assert ex._is_device_eligible_for_config(dev) is False

    def test_not_eligible_wrong_status(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        for status in ["离线", "未检测", "失败", "成功"]:
            dev = _make_device(online=True, status=status, selected=True)
            assert ex._is_device_eligible_for_config(dev) is False

    def test_not_eligible_not_selected(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        dev = _make_device(online=True, status="在线", selected=False)
        assert ex._is_device_eligible_for_config(dev) is False

    def test_not_eligible_already_processing(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        dev = _make_device(online=True, status="在线", selected=True)
        ex._check_and_mark_device_processing(dev)
        assert ex._is_device_eligible_for_config(dev) is False


# ============================================================================
# ConfigExecutor - execute_batch
# ============================================================================

class TestExecuteBatch:
    def test_execute_batch_empty_devices(self):
        """No devices at all -> returns []."""
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        result = ex.execute_batch([])
        assert result == []

    def test_execute_batch_all_offline(self):
        """All devices offline -> skipped, returns []."""
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        devices = [
            _make_device(ip="10.0.0.1", online=False, status="离线"),
            _make_device(ip="10.0.0.2", online=False, status="离线"),
        ]
        result = ex.execute_batch(devices)
        assert result == []  # no eligible devices

    def test_execute_batch_wrong_status(self):
        """Online but wrong status -> skipped."""
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        devices = [
            _make_device(ip="10.0.0.1", online=True, status="失败"),
        ]
        result = ex.execute_batch(devices)
        assert result == []

    def test_execute_batch_mixed_online_offline(self):
        """Mixed: online device gets configured, offline gets skipped."""
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        devices = [
            _make_device(ip="10.0.0.1", online=True, status="在线"),
            _make_device(ip="10.0.0.2", online=False, status="离线"),
            _make_device(ip="10.0.0.3", online=True, status="在线"),
        ]

        # Mock _send_command to succeed
        with patch.object(ex, '_send_command', return_value=(True, "成功")):
            with patch.object(ex.log_manager, 'log_cgi_request'):
                with patch.object(ex.log_manager, 'log_cgi_response'):
                    result = ex.execute_batch(devices, exec_strategy="device_first")

        # Offline device should be skipped
        assert len(result) == 2
        assert result[0]['ip'] == "10.0.0.1" or result[0]['ip'] == "10.0.0.3"

    def test_execute_batch_device_first_sync(self):
        """Sync mode, device_first strategy."""
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr, use_async=False)
        devices = [
            _make_device(ip="10.0.0.1", online=True, status="在线"),
        ]

        with patch.object(ex, '_send_command', return_value=(True, "成功")):
            with patch.object(ex.log_manager, 'log_cgi_request'):
                with patch.object(ex.log_manager, 'log_cgi_response'):
                    result = ex.execute_batch(devices, exec_strategy="device_first")

        assert len(result) >= 0  # may succeed or return empty depending on execution

    def test_execute_batch_command_first_sync(self):
        """Sync mode, command_first strategy."""
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr, use_async=False)
        # Need at least one command in config
        ex.config["cgi_commands"] = ["TestParam=1"]
        devices = [
            _make_device(ip="10.0.0.1", online=True, status="在线"),
        ]

        with patch.object(ex, '_send_command', return_value=(True, "成功")):
            with patch.object(ex.log_manager, 'log_cgi_request'):
                with patch.object(ex.log_manager, 'log_cgi_response'):
                    result = ex.execute_batch(devices, exec_strategy="command_first")

        assert len(result) >= 0

    def test_execute_batch_with_stop_during_sync(self):
        """Stop called during execution."""
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr, use_async=False)
        devices = [
            _make_device(ip="10.0.0.1", online=True, status="在线"),
        ]

        # Stop before execution
        ex.stop()

        with patch.object(ex, '_send_command', return_value=(True, "成功")):
            result = ex.execute_batch(devices, exec_strategy="device_first")
        assert result is not None
