"""测试：执行器运行时调用 stop() 的停止行为"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import threading
import asyncio
import pytest

from aiohttp import web
from utils.device_manager import ConfigExecutor, DeviceInfo
from utils.log_manager import LogManager

# 延迟导入 mock_cgi_server handler（避免 tests 包路径冲突）
_HANDLE_CONFIG = None


def _get_handler():
    global _HANDLE_CONFIG
    if _HANDLE_CONFIG is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "mock_cgi_server",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_cgi_server.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _HANDLE_CONFIG = mod.handle_config
    return _HANDLE_CONFIG


MOCK_PORT = 8081  # 用不同端口避免与 test_with_mock_server 冲突


@pytest.fixture(scope="module")
def mock_server():
    """启动 mock CGI server（模块级 fixture）"""
    server = {}

    def _run():
        loop = asyncio.new_event_loop()
        server["loop"] = loop
        asyncio.set_event_loop(loop)

        app = web.Application()
        app.router.add_get("/cgi-bin/configManager.cgi", _get_handler())

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
    yield server

    if "loop" in server:
        loop = server["loop"]
        loop.call_soon_threadsafe(loop.stop)
        server["thread"].join(timeout=2)


def test_stop_while_running(mock_server):
    """启动执行器，执行过程中调用 stop()，验证能正确停止"""
    devices = [
        DeviceInfo(
            index=i, ip="127.0.0.1", port=str(MOCK_PORT),
            username="admin", password="admin", online=True, status="在线",
        )
        for i in range(2)
    ]

    cfg = {
        "cgi_commands": [f"param={i}" for i in range(100)],
        "config_concurrent": 10,
        "timeout": 5000,
        "auth_method": "digest",
        "verify_ssl": False,
    }
    log = LogManager()
    exe = ConfigExecutor(cfg, log, use_async=True)

    result_container = {}

    def _run():
        try:
            res = exe.execute_batch(
                devices,
                mode="standard",
                exec_strategy="device_first",
                progress_callback=lambda t, p, s: None,
                stop_callback=None,
            )
            result_container["res"] = res
        except Exception as e:
            result_container["err"] = str(e)

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    # 等一会后请求停止
    time.sleep(0.5)
    exe.stop()
    t.join(timeout=5)

    # 验证线程已结束
    assert t.is_alive() is False, "执行器线程在 stop() 后应结束"
    # stop 后应不再继续工作
    if hasattr(exe, "_is_stopped"):
        assert exe._is_stopped() is True
