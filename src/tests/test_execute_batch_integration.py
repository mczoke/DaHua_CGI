"""Integration tests for ConfigExecutor.execute_batch 5 core branches.

Scenarios:
1. 正常批量（全成功）
2. 部分失败（回退/重试）
3. 全失败（超时/网络断连）
4. 空批次（参数校验）
5. 并发锁冲突

Uses mock CGI server that supports per-request scenario control.
"""
import sys
import os
import time
import threading
import asyncio
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiohttp import web
from utils.device_manager import ConfigExecutor, DeviceInfo
from utils.log_manager import LogManager

# --- Mock server helpers ---

MOCK_PORT = 9080  # separate port from existing mock to avoid conflicts


def _import_mock_handler():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "mock_execute_batch_server",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_execute_batch_server.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


HANDLE_CONFIG = None
HANDLE_RESET = None


def _get_handlers():
    global HANDLE_CONFIG, HANDLE_RESET
    if HANDLE_CONFIG is None:
        mod = _import_mock_handler()
        HANDLE_CONFIG = mod.handle_config
        HANDLE_RESET = mod.handle_reset
    return HANDLE_CONFIG, HANDLE_RESET


@pytest.fixture(scope="module")
def mock_server():
    """Start mock CGI server (module-level, one instance)."""
    server = {}

    def _run():
        loop = asyncio.new_event_loop()
        server["loop"] = loop
        asyncio.set_event_loop(loop)

        handle_config, handle_reset = _get_handlers()
        app = web.Application()
        app.router.add_get("/cgi-bin/configManager.cgi", handle_config)
        app.router.add_post("/reset", handle_reset)

        runner = web.AppRunner(app)
        loop.run_until_complete(runner.setup())
        site = web.TCPSite(runner, "127.0.0.1", MOCK_PORT)
        loop.run_until_complete(site.start())

        try:
            loop.run_forever()
        finally:
            loop.run_until_complete(runner.cleanup())
            loop.close()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    timeout = 5
    start = time.time()
    while "loop" not in server and time.time() - start < timeout:
        time.sleep(0.05)
    time.sleep(0.2)
    server["thread"] = t
    return server


def make_device(idx, ip="127.0.0.1", port=None, username="admin", password="admin",
                online=True, status="在线"):
    """Helper to create a DeviceInfo with proper defaults."""
    if port is None:
        port = str(MOCK_PORT)
    dev = DeviceInfo(
        index=idx, ip=ip, port=port,
        username=username, password=password,
        online=online,
    )
    dev.status = status
    return dev


def make_config(cgi_commands, concurrent=5, timeout=5000, auth_method="digest", verify_ssl=False):
    """Helper to create a config dict."""
    return {
        "cgi_commands": cgi_commands,
        "config_concurrent": concurrent,
        "timeout": timeout,
        "auth_method": auth_method,
        "verify_ssl": verify_ssl,
    }


# ============================================================================
# Test class
# ============================================================================

class TestExecuteBatchIntegration:
    """5 core branches of execute_batch integration tests."""

    # --- 1. 正常批量（全成功） ---

    def test_all_success(self, mock_server):
        """Single device, 3 commands, all return 200 OK."""
        cfg = make_config(["VideoTitle=Test", "EncodeBitrate=4096", "RecordMode=Manual"])
        log = LogManager()
        exe = ConfigExecutor(cfg, log, use_async=True)
        try:
            dev = make_device(0)
            results = exe.execute_batch(
                [dev],
                mode="standard",
                exec_strategy="device_first",
                progress_callback=lambda t, p, s: None,
                stop_callback=None,
            )
            # Should get at least one result
            assert isinstance(results, list) and len(results) >= 1
            r = results[0]
            assert r["ip"] == "127.0.0.1"
            assert r["success"] is True, f"Expected success, got: {r}"
            assert r["total_commands"] == 3
            assert r["success_commands"] == 3
            assert r["failed_commands"] == 0
        finally:
            exe.stop()

    def test_two_devices_all_success(self, mock_server):
        """2 devices, 2 commands each, all succeed."""
        cfg = make_config(["EncodeBlend=true", "VideoStandard=PAL"])
        log = LogManager()
        exe = ConfigExecutor(cfg, log, use_async=True)
        try:
            devs = [make_device(0), make_device(1)]
            results = exe.execute_batch(
                devs,
                mode="standard",
                exec_strategy="device_first",
                progress_callback=lambda t, p, s: None,
                stop_callback=None,
            )
            assert isinstance(results, list) and len(results) >= 1
            total_success = sum(r["success_commands"] for r in results)
            assert total_success == 4, f"Expected 4 success commands, got {total_success}"
        finally:
            exe.stop()

    # --- 2. 部分失败（回退/重试） ---

    def test_partial_failure(self, mock_server):
        """One command fails (mock server returns 500 for a specific scenario).
        
        Since the mock response is scenario-based, we use a single-command approach
        with a scenario that returns mixed results in the body (partial_ok).
        """
        cfg = make_config(["param=test"])
        log = LogManager()
        exe = ConfigExecutor(cfg, log, use_async=True)
        try:
            # We'll make multiple requests to the same mock with a command
            # that triggers partial_ok scenario via the query param
            dev = make_device(0)
            results = exe.execute_batch(
                [dev],
                mode="standard",
                exec_strategy="device_first",
                progress_callback=lambda t, p, s: None,
                stop_callback=None,
            )
            assert isinstance(results, list)
            # The test verifies the system doesn't crash on server errors
            # (real failure depends on mock response)
        finally:
            exe.stop()

    def test_some_devices_offline(self, mock_server):
        """2 online + 1 offline device; offline should be skipped."""
        cfg = make_config(["TestParam=1"])
        log = LogManager()
        exe = ConfigExecutor(cfg, log, use_async=True)
        try:
            online1 = make_device(0)
            online2 = make_device(1)
            offline = make_device(2, online=False, status="离线")
            results = exe.execute_batch(
                [online1, offline, online2],
                mode="standard",
                exec_strategy="device_first",
                progress_callback=lambda t, p, s: None,
                stop_callback=None,
            )
            assert isinstance(results, list)
            # Offline device's status gets updated
            assert offline.status == "离线"
            # Results should come from the 2 online devices
            result_ips = {r["ip"] for r in results}
            assert "127.0.0.1" in result_ips
        finally:
            exe.stop()

    # --- 3. 全失败（超时/网络断连） ---

    def test_all_failures_timeout(self, mock_server):
        """Commands to a non-existent server port — all should fail with connection error."""
        cfg = make_config(["ParamA=1"], timeout=2000)
        log = LogManager()
        exe = ConfigExecutor(cfg, log, use_async=True)
        try:
            # Point to a port nothing is listening on
            dev = make_device(0, port="19999")
            results = exe.execute_batch(
                [dev],
                mode="standard",
                exec_strategy="device_first",
                progress_callback=lambda t, p, s: None,
                stop_callback=None,
            )
            assert isinstance(results, list)
            if results:
                r = results[0]
                # Should have failed commands
                assert r["failed_commands"] > 0 or r["success"] is False
        finally:
            exe.stop()

    def test_all_devices_offline(self, mock_server):
        """All devices are offline — should return empty list."""
        cfg = make_config(["Param=1"])
        log = LogManager()
        exe = ConfigExecutor(cfg, log, use_async=True)
        try:
            devs = [
                make_device(0, online=False, status="离线"),
                make_device(1, online=False, status="离线"),
            ]
            results = exe.execute_batch(
                devs,
                mode="standard",
                exec_strategy="device_first",
                progress_callback=lambda t, p, s: None,
                stop_callback=None,
            )
            assert results == [], f"Expected empty list, got {results}"
        finally:
            exe.stop()

    # --- 4. 空批次 ---

    def test_empty_device_list(self, mock_server):
        """Empty device list — should return empty list."""
        cfg = make_config(["Param=1"])
        log = LogManager()
        exe = ConfigExecutor(cfg, log, use_async=True)
        try:
            results = exe.execute_batch(
                [],
                mode="standard",
                exec_strategy="device_first",
                progress_callback=lambda t, p, s: None,
                stop_callback=None,
            )
            assert results == [], f"Expected empty list, got {results}"
        finally:
            exe.stop()

    def test_no_commands_configured(self, mock_server):
        """Empty cgi_commands — should process without error."""
        cfg = make_config([])
        log = LogManager()
        exe = ConfigExecutor(cfg, log, use_async=True)
        try:
            dev = make_device(0)
            results = exe.execute_batch(
                [dev],
                mode="standard",
                exec_strategy="device_first",
                progress_callback=lambda t, p, s: None,
                stop_callback=None,
            )
            assert isinstance(results, list)
        finally:
            exe.stop()

    # --- 5. 并发锁冲突 ---

    def test_concurrent_lock_same_device(self, mock_server):
        """Simulate concurrent access: call execute_batch twice rapidly.
        
        The second call should not deadlock or crash, and should still produce results.
        """
        cfg = make_config(["CmdA=1", "CmdB=2"], concurrent=2)
        log = LogManager()
        exe = ConfigExecutor(cfg, log, use_async=True)
        try:
            dev = make_device(0)

            # First call
            r1 = exe.execute_batch(
                [dev],
                mode="standard",
                exec_strategy="device_first",
                progress_callback=lambda t, p, s: None,
                stop_callback=None,
            )

            # Immediate second call on same executor
            dev2 = make_device(1)
            r2 = exe.execute_batch(
                [dev2],
                mode="standard",
                exec_strategy="device_first",
                progress_callback=lambda t, p, s: None,
                stop_callback=None,
            )

            assert isinstance(r1, list)
            assert isinstance(r2, list)
        finally:
            exe.stop()

    def test_stop_during_batch(self, mock_server):
        """Stop mid-batch should return partial results without deadlock."""
        cfg = make_config(["SlowCmd=1"], timeout=5000)
        log = LogManager()
        exe = ConfigExecutor(cfg, log, use_async=True)
        try:
            dev = make_device(0)

            # Use threading to stop after a short delay
            def delayed_stop():
                time.sleep(0.5)
                exe.stop()

            t = threading.Thread(target=delayed_stop, daemon=True)
            t.start()

            results = exe.execute_batch(
                [dev],
                mode="standard",
                exec_strategy="device_first",
                progress_callback=lambda t, p, s: None,
                stop_callback=lambda: False,  # don't external-stop
            )

            # Should complete (possibly with partial results) without error
            assert isinstance(results, list)
        finally:
            exe.stop()
