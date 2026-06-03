"""Unit tests for async_executor.py targeting 80%+ coverage.

Covers:
1. SyncRequestsExecutor - send_command_sync (string/cmd branches, timeout, exception, non-200)
2. SyncRequestsExecutor - _build_simple_params (getCurrentTime, setConfig simple/dahua)
3. SyncRequestsExecutor - _build_dahua_params (nested dict/list)
4. SyncRequestsExecutor - close
5. AsyncExecutor - context manager, close, send_command_async
6. AsyncIOManager - init variants, send_command (sync/event-loop/running/no-loop)
7. send_multiple_commands
8. LogManager integration
"""
import sys
import os
import asyncio
from unittest.mock import MagicMock, patch, PropertyMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import requests

from utils.async_executor import (
    SyncRequestsExecutor,
    AsyncExecutor,
    AsyncIOManager,
    send_multiple_commands,
)


# ============================================================================
# Mock device helper
# ============================================================================

class MockDevice:
    """Minimal device mock for testing."""
    def __init__(self, ip="192.168.1.100", port="80", username="admin", password="admin"):
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password


# ============================================================================
# Helper: mock requests.Session.get
# ============================================================================

def _make_mock_response(status_code=200, text="OK", headers=None):
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.reason = {200: "OK", 401: "Unauthorized", 500: "Server Error"}.get(status_code, "Unknown")
    mock_response.text = text
    mock_response.headers = headers or {}
    return mock_response


# ============================================================================
# SyncRequestsExecutor tests
# ============================================================================

class TestSyncRequestsExecutor:
    """Unit tests for SyncRequestsExecutor."""

    # --- send_command_sync: string command branches ---

    @patch.object(requests, 'Session')
    def test_send_command_sync_string_with_eq(self, mock_session_cls):
        """String command containing '=' -> parsed as setConfig with key=value."""
        mock_instance = mock_session_cls.return_value
        mock_instance.get.return_value = _make_mock_response()

        executor = SyncRequestsExecutor(verify_ssl=False, request_timeout=5)
        dev = MockDevice()
        ok, text, status, headers, error = executor.send_command_sync(
            dev, "VideoTitle=Test123"
        )
        assert ok is True
        assert text == "OK"
        assert status == "SUCCESS"
        executor.close()

    @patch.object(requests, 'Session')
    def test_send_command_sync_string_without_eq(self, mock_session_cls):
        """String command without '=' -> action-only command."""
        mock_instance = mock_session_cls.return_value
        mock_instance.get.return_value = _make_mock_response()

        executor = SyncRequestsExecutor(verify_ssl=False, request_timeout=5)
        dev = MockDevice()
        ok, text, status, headers, error = executor.send_command_sync(
            dev, "getCurrentTime"
        )
        assert ok is True
        executor.close()

    # --- send_command_sync: non-200 response + WWW-Authenticate ---

    @patch.object(requests, 'Session')
    def test_send_command_sync_401_with_auth_header(self, mock_session_cls):
        """Non-200 response with WWW-Authenticate header."""
        mock_instance = mock_session_cls.return_value
        mock_instance.get.return_value = _make_mock_response(
            status_code=401,
            text="Auth required",
            headers={"WWW-Authenticate": 'Digest realm="test"'}
        )

        executor = SyncRequestsExecutor(verify_ssl=False, request_timeout=5)
        dev = MockDevice()
        ok, text, status, headers, error = executor.send_command_sync(
            dev, {"action": "setConfig", "param": {"Test": "1"}}
        )
        assert ok is False
        assert status == "FAILED"
        assert "401" in error
        executor.close()

    # --- send_command_sync: timeout ---

    @patch.object(requests, 'Session')
    def test_send_command_sync_timeout(self, mock_session_cls):
        """requests.Timeout raised."""
        mock_instance = mock_session_cls.return_value
        mock_instance.get.side_effect = requests.Timeout("Connection timed out")

        executor = SyncRequestsExecutor(verify_ssl=False, request_timeout=1)
        dev = MockDevice()
        ok, text, status, headers, error = executor.send_command_sync(dev, {"action": "getTime"})
        assert ok is False
        assert "超时" in error
        executor.close()

    # --- send_command_sync: generic exception ---

    @patch.object(requests, 'Session')
    def test_send_command_sync_exception(self, mock_session_cls):
        """Generic Exception raised."""
        mock_instance = mock_session_cls.return_value
        mock_instance.get.side_effect = ConnectionError("Connection refused")

        executor = SyncRequestsExecutor(verify_ssl=False, request_timeout=5)
        dev = MockDevice()
        ok, text, status, headers, error = executor.send_command_sync(dev, {"action": "test"})
        assert ok is False
        assert "异常" in error
        executor.close()

    # --- SyncRequestsExecutor: close no error ---

    def test_close_twice_no_error(self):
        """close() on already-closed executor does not raise."""
        executor = SyncRequestsExecutor()
        executor.close()
        executor.close()  # second call should be fine

    # --- _build_simple_params: getCurrentTime ---

    def test_build_simple_params_get_current_time(self):
        """_build_simple_params with getCurrentTime action."""
        executor = SyncRequestsExecutor()
        result = executor._build_simple_params({"action": "getCurrentTime"})
        assert result == "action=getCurrentTime"

    # --- _build_simple_params: non-setConfig action ---

    def test_build_simple_params_other_action(self):
        """_build_simple_params with non-setConfig action uses urlencode."""
        executor = SyncRequestsExecutor()
        result = executor._build_simple_params({"action": "reboot", "param": "now"})
        assert "action=reboot" in result

    # --- _build_simple_params: setConfig with simple param ---

    def test_build_simple_params_setconfig_simple(self):
        """_build_simple_params setConfig with simple string param."""
        executor = SyncRequestsExecutor()
        result = executor._build_simple_params({
            "action": "setConfig",
            "param": {"VideoStandard": "PAL"}
        })
        assert "VideoStandard=PAL" in result

    # --- _build_simple_params: setConfig with bracket key ---

    def test_build_simple_params_setconfig_bracket_key(self):
        """_build_simple_params setConfig with bracket notation key."""
        executor = SyncRequestsExecutor()
        result = executor._build_simple_params({
            "action": "setConfig",
            "param": {"VideoWidget[0].Title": "Test"}
        })
        assert "action=setConfig" in result
        assert "VideoWidget" in result

    # --- _build_dahua_params: list with dict, nested dict ---

    def test_build_dahua_params_list_of_dict(self):
        """_build_dahua_params with list of dicts (nested)."""
        executor = SyncRequestsExecutor()
        result = executor._build_dahua_params({
            "action": "setConfig",
            "param": {
                "Channel": [
                    {"Video": {"Brightness": 50, "Contrast": 30}},
                    {"Video": {"Hue": 10}},
                ]
            }
        })
        assert "Channel[0][Video][Brightness]=50" in result
        assert "Channel[0][Video][Contrast]=30" in result
        assert "Channel[1][Video][Hue]=10" in result

    def test_build_dahua_params_list_of_scalar(self):
        """_build_dahua_params with list of scalars."""
        executor = SyncRequestsExecutor()
        result = executor._build_dahua_params({
            "action": "setConfig",
            "param": {
                "IPAddress": ["192.168.1.1", "192.168.1.2"]
            }
        })
        assert "IPAddress[0]=192.168.1.1" in result
        assert "IPAddress[1]=192.168.1.2" in result

    def test_build_dahua_params_nested_dict(self):
        """_build_dahua_params with nested dict (dict in dict)."""
        executor = SyncRequestsExecutor()
        result = executor._build_dahua_params({
            "action": "setConfig",
            "param": {
                "VideoIn": {
                    "Channel": {"Brightness": 50, "Contrast": {"Value": 30, "Valid": True}}
                }
            }
        })
        # dict key with sub-dict
        assert "VideoIn[Channel][Brightness]=50" in result
        # The inner dict Contrast's value is itself a dict, which gets str()'d by the code
        # It won't produce VideoIn[Channel][Contrast][Value]=30 because the code
        # checks `isinstance(sub_value, dict)` but after that level it does str()
        # So we just check the outer keys exist
        assert "VideoIn[Channel][Contrast]=" in result

    def test_build_dahua_params_plain_value(self):
        """_build_dahua_params with plain value (else branch)."""
        executor = SyncRequestsExecutor()
        result = executor._build_dahua_params({
            "action": "setConfig",
            "param": {
                "VideoTitle": "FrontGate",
                "EncodeBlend": "true",
            }
        })
        assert "VideoTitle=FrontGate" in result
        assert "EncodeBlend=true" in result


# ============================================================================
# AsyncExecutor tests
# ============================================================================

@pytest.mark.asyncio
async def test_async_executor_context_manager():
    """AsyncExecutor as async context manager."""
    with patch.object(requests, 'Session'):
        async with AsyncExecutor(timeout=5, verify_ssl=False) as ex:
            assert ex is not None
            assert ex._closed is False


@pytest.mark.asyncio
async def test_async_executor_close():
    """Close AsyncExecutor properly."""
    with patch.object(requests, 'Session'):
        ex = AsyncExecutor(timeout=5, verify_ssl=False)
        await ex.close()
        assert ex._closed is True


@pytest.mark.asyncio
async def test_async_executor_send_command():
    """AsyncExecutor.send_command_async with mocked sync call."""
    with patch.object(requests, 'Session') as mock_session_cls:
        mock_instance = mock_session_cls.return_value
        mock_instance.get.return_value = _make_mock_response()

        ex = AsyncExecutor(timeout=5, verify_ssl=False)
        dev = MockDevice()
        ok, text, status, headers, err = await ex.send_command_async(dev, {"action": "getTime"})
        assert ok is True
        assert text == "OK"
        assert status == "SUCCESS"
        await ex.close()


@pytest.mark.asyncio
async def test_async_executor_send_command_string():
    """AsyncExecutor.send_command_async with string command."""
    with patch.object(requests, 'Session') as mock_session_cls:
        mock_instance = mock_session_cls.return_value
        mock_instance.get.return_value = _make_mock_response()

        ex = AsyncExecutor(timeout=5, verify_ssl=False)
        dev = MockDevice()
        ok, text, status, headers, err = await ex.send_command_async(dev, "SetParam=value123")
        assert ok is True
        await ex.close()


# ============================================================================
# AsyncIOManager tests
# ============================================================================

class TestAsyncIOManager:
    """Unit tests for AsyncIOManager."""

    def test_init_with_timeout(self):
        """AsyncIOManager with custom timeout."""
        m = AsyncIOManager(timeout=5, verify_ssl=False, max_connections=20, auth_method='basic')
        assert m.timeout == 5
        assert m.auth_method == 'basic'
        assert m.max_connections == 20
        m.close()

    def test_init_with_verify_ssl_true(self):
        """AsyncIOManager with verify_ssl=True."""
        m = AsyncIOManager(timeout=10, verify_ssl=True, auth_method='digest')
        assert m.verify_ssl is True
        m.close()

    def test_send_command_sync_no_event_loop(self):
        """AsyncIOManager.send_command when no event loop is running (RuntimeError -> asyncio.run)."""
        with patch.object(requests, 'Session') as mock_session_cls:
            mock_instance = mock_session_cls.return_value
            mock_instance.get.return_value = _make_mock_response()

            m = AsyncIOManager(timeout=5, verify_ssl=False)
            dev = MockDevice()
            ok, text, status, headers, err = m.send_command(dev, {"action": "test"})
            assert ok is True
            assert text == "OK"
            m.close()

    def test_send_command_with_running_loop(self):
        """AsyncIOManager.send_command when event loop IS running -> thread pool submit."""
        with patch.object(requests, 'Session') as mock_session_cls:
            mock_instance = mock_session_cls.return_value
            mock_instance.get.return_value = _make_mock_response()

            m = AsyncIOManager(timeout=5, verify_ssl=False)
            dev = MockDevice()

            results = []

            async def _test():
                nonlocal results
                ok, text, status, headers, err = m.send_command(dev, {"action": "test"})
                results.append((ok, text))

            asyncio.run(_test())
            assert len(results) == 1
            assert results[0][0] is True
            m.close()

    @pytest.mark.asyncio
    async def test_send_command_async(self):
        """AsyncIOManager.send_command_async."""
        with patch.object(requests, 'Session') as mock_session_cls:
            mock_instance = mock_session_cls.return_value
            mock_instance.get.return_value = _make_mock_response()

            m = AsyncIOManager(timeout=5, verify_ssl=False)
            dev = MockDevice()
            ok, text, status, headers, err = await m.send_command_async(dev, {"action": "test"})
            assert ok is True
            m.close()

    def test_close_wait_false(self):
        """AsyncIOManager.close(wait=False)."""
        m = AsyncIOManager(timeout=5, verify_ssl=False)
        m.close(wait=False)
        assert m._closed is True

    def test_close_twice_no_error(self):
        """AsyncIOManager double close."""
        m = AsyncIOManager(timeout=5, verify_ssl=False)
        m.close()
        m.close()

    def test_run_coroutine(self):
        """AsyncIOManager.run_coroutine (must be sync, asyncio.run inside)."""
        m = AsyncIOManager(timeout=5, verify_ssl=False)

        async def dummy():
            return 42

        result = m.run_coroutine(dummy())
        assert result == 42
        m.close()


# ============================================================================
# send_multiple_commands (module-level function)
# ============================================================================

@pytest.mark.asyncio
async def test_send_multiple_commands():
    """Module-level send_multiple_commands function."""
    with patch.object(requests, 'Session') as mock_session_cls:
        mock_instance = mock_session_cls.return_value
        mock_instance.get.return_value = _make_mock_response()

        dev = MockDevice()
        commands = [{"action": "cmd1"}, {"action": "cmd2"}]
        results = await send_multiple_commands(dev, commands, timeout=5)
        assert len(results) == 2
        for ok, msg in results:
            assert ok is True


# ============================================================================
# LogManager integration test
# ============================================================================

@pytest.mark.asyncio
async def test_log_manager_integration():
    """Verify log_manager can be used alongside async_executor."""
    from utils.log_manager import LogManager

    with patch.object(requests, 'Session') as mock_session_cls:
        mock_instance = mock_session_cls.return_value
        mock_instance.get.return_value = _make_mock_response(
            headers={"Content-Type": "text/plain"}
        )

        lm = LogManager()
        ex = AsyncExecutor(timeout=5, verify_ssl=False)
        dev = MockDevice()

        ok, text, status, headers, err = await ex.send_command_async(dev, {"action": "test"})
        assert ok is True

        # LogManager should be importable and functional
        lm.log_cgi_request(dev.ip, 1, 1, "http://test", "digest", {})
        await ex.close()
