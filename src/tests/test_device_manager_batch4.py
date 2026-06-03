"""Unit tests for device_manager.py - Batch 4: Async execution + _generate_custom_command

Covers:
- _generate_custom_command (all placeholders found, missing variable, no placeholders)
- _async_config_device (async variant, success, stop, offline mid-execution)
- _async_execute_by_device (async device-first strategy)
- _async_send_command_with_url_auth (success, error)
"""
import sys
import os
import asyncio
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
        "cgi_commands": ["TestParam=1", "VideoTitle=Test"],
    }
    cfg.update(overrides)
    return cfg


def _make_async_executor(**kw):
    """Create ConfigExecutor configured for async."""
    cfg = _make_config(**{k: v for k, v in kw.items() if k != 'log_mgr'})
    log_mgr = kw.get('log_mgr', MagicMock())
    # Don't allow real AsyncIOManager init unless testing async
    return ConfigExecutor(cfg, log_mgr, use_async=True)


# ============================================================================
# _generate_custom_command
# ============================================================================

class TestGenerateCustomCommand:
    def test_no_placeholders(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        cmd = ex._generate_custom_command("VideoStandard=PAL", {})
        assert cmd == "VideoStandard=PAL"

    def test_all_placeholders_found(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        cmd = ex._generate_custom_command(
            "VideoWidget[{channel}].Title={title}",
            {"channel": "0", "title": "FrontGate"}
        )
        assert cmd == "VideoWidget[0].Title=FrontGate"

    def test_missing_variable_returns_none(self):
        log_mgr = MagicMock()
        ex = ConfigExecutor(_make_config(), log_mgr)
        cmd = ex._generate_custom_command(
            "VideoWidget[{channel}].Title={title}",
            {"channel": "0"}  # missing "title"
        )
        assert cmd is None


# ============================================================================
# _async_config_device
# ============================================================================

@pytest.mark.asyncio
class TestAsyncConfigDevice:
    async def test_success(self):
        log_mgr = MagicMock()
        ex = _make_async_executor(log_mgr=log_mgr)
        dev = _make_device(ip="10.0.0.1")

        with patch.object(ex, '_async_send_command_with_url_auth',
                          return_value=(True, "成功")):
            result = await ex._async_config_device(dev)

        assert result is not None
        assert result['success'] is True

    async def test_device_not_eligible(self):
        log_mgr = MagicMock()
        ex = _make_async_executor(log_mgr=log_mgr)
        dev = _make_device(ip="10.0.0.1", online=False)

        with patch.object(ex, '_async_send_command_with_url_auth',
                          return_value=(True, "成功")):
            result = await ex._async_config_device(dev)

        assert result is None  # not eligible

    async def test_all_fail(self):
        log_mgr = MagicMock()
        ex = _make_async_executor(log_mgr=log_mgr)
        dev = _make_device(ip="10.0.0.1")

        with patch.object(ex, '_async_send_command_with_url_auth',
                          return_value=(False, "error")):
            result = await ex._async_config_device(dev)

        assert result is not None
        assert result['success'] is False

    async def test_offline_mid_execution(self):
        log_mgr = MagicMock()
        ex = _make_async_executor(log_mgr=log_mgr)
        dev = _make_device(ip="10.0.0.1")

        call_count = [0]

        async def mock_send(*args):
            call_count[0] += 1
            if call_count[0] >= 1:
                dev.online = False
            return (True, "成功")

        with patch.object(ex, '_async_send_command_with_url_auth',
                          side_effect=mock_send):
            result = await ex._async_config_device(dev)

        assert result is not None

    async def test_stop_mid_execution(self):
        log_mgr = MagicMock()
        ex = _make_async_executor(log_mgr=log_mgr)
        dev = _make_device(ip="10.0.0.1")

        async def mock_send(*args):
            ex.stop()
            return (True, "成功")

        with patch.object(ex, '_async_send_command_with_url_auth',
                          side_effect=mock_send):
            result = await ex._async_config_device(dev)

        assert result is not None

    async def test_exception(self):
        log_mgr = MagicMock()
        ex = _make_async_executor(log_mgr=log_mgr)
        dev = _make_device(ip="10.0.0.1")

        with patch.object(ex, '_async_send_command_with_url_auth',
                          side_effect=Exception("async error")):
            result = await ex._async_config_device(dev)

        assert result is not None
        assert result['success'] is False


# ============================================================================
# _async_send_command_with_url_auth
# ============================================================================

@pytest.mark.asyncio
class TestAsyncSendWithUrlAuth:
    @pytest.fixture
    def ex(self):
        log_mgr = MagicMock()
        e = _make_async_executor(log_mgr=log_mgr)
        e.async_manager = MagicMock()
        return e

    async def test_success(self, ex):
        async def _send(*a, **kw):
            return (True, "OK", 200, {}, "success body")
        ex.async_manager.send_command_async = _send

        dev = _make_device(ip="10.0.0.1")
        ok, msg = await ex._async_send_command_with_url_auth(dev, "TestParam=1", 1, 2)
        assert ok is True

    async def test_error(self, ex):
        async def _send(*a, **kw):
            return (False, "Bad request", 400, {}, "error body")
        ex.async_manager.send_command_async = _send

        dev = _make_device(ip="10.0.0.1")
        ok, msg = await ex._async_send_command_with_url_auth(dev, "BadParam=1", 1, 2)
        assert ok is False

    async def test_old_return_format(self, ex):
        async def _send(*a, **kw):
            return (True, "old-format")
        ex.async_manager.send_command_async = _send

        dev = _make_device(ip="10.0.0.1")
        ok, msg = await ex._async_send_command_with_url_auth(dev, "Test=1", 1, 2)
        assert ok is True

    async def test_exception(self, ex):
        async def _send(*a, **kw):
            raise Exception("network error")
        ex.async_manager.send_command_async = _send

        dev = _make_device(ip="10.0.0.1")
        ok, msg = await ex._async_send_command_with_url_auth(dev, "Test=1", 1, 2)
        assert ok is False


# ============================================================================
# _async_execute_by_device
# ============================================================================

@pytest.mark.asyncio
async def test_async_execute_by_device_empty():
    log_mgr = MagicMock()
    ex = _make_async_executor(log_mgr=log_mgr)

    devices = [_make_device(ip="10.0.0.1", online=False)]  # not eligible
    results = await ex._async_execute_by_device(devices)
    assert results == []


@pytest.mark.asyncio
async def test_async_execute_by_device_single():
    log_mgr = MagicMock()
    ex = _make_async_executor(log_mgr=log_mgr)
    dev = _make_device(ip="10.0.0.1")

    with patch.object(ex, '_async_config_device') as mock_acd:
        mock_acd.return_value = {
            'device': dev,
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
        results = await ex._async_execute_by_device([dev])

    assert len(results) == 1
    assert results[0]['success'] is True
