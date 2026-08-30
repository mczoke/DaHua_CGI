"""测试：在 mock CGI server 上运行 ConfigExecutor 的 digest/basic 认证流程"""
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

# 直接从 mock_cgi_server 模块复制 handler 函数引用
# 用 module-level import 避免 tests 包路径冲突
MOCK_CGI_MODULE = None


def _import_mock_handler():
    """通过绝对路径导入 mock_cgi_server 模块"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "mock_cgi_server",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_cgi_server.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# 延迟导入，避免 pytest 收集时的包冲突
HANDLE_CONFIG = None


def _get_handle_config():
    global HANDLE_CONFIG, MOCK_CGI_MODULE
    if HANDLE_CONFIG is None:
        MOCK_CGI_MODULE = _import_mock_handler()
        HANDLE_CONFIG = MOCK_CGI_MODULE.handle_config
    return HANDLE_CONFIG


MOCK_PORT = 8080


@pytest.fixture(scope="module")
def mock_server():
    """启动 mock CGI server（模块级 fixture，只启动一次）"""
    server = _start_mock_server()
    yield server
    _stop_mock_server(server)


def _start_mock_server():
    server = {}

    def _run():
        loop = asyncio.new_event_loop()
        server["loop"] = loop
        asyncio.set_event_loop(loop)

        handle_config = _get_handle_config()
        app = web.Application()
        app.router.add_get("/cgi-bin/configManager.cgi", handle_config)

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


def _stop_mock_server(server):
    if not server or "loop" not in server:
        return
    loop = server["loop"]
    loop.call_soon_threadsafe(loop.stop)
    server["thread"].join(timeout=2)


@pytest.fixture
def device():
    return DeviceInfo(
        index=0, ip="127.0.0.1", port=str(MOCK_PORT),
        username="admin", password="admin", online=True, status="在线",
        selected=True,
    )


@pytest.fixture
def log():
    return LogManager()


class TestExecutorWithMockServer:
    """在 mock CGI server 上测试 ConfigExecutor 的认证流程"""

    def test_digest_auth(self, mock_server, device, log):
        """Digest 认证：从 401 挑战→带认证重试→成功"""
        cfg = {
            "cgi_commands": ["param=1"],
            "config_concurrent": 5,
            "timeout": 5000,
            "auth_method": "digest",
            "verify_ssl": False,
        }
        exe = ConfigExecutor(cfg, log, use_async=True)
        try:
            res = exe.execute_batch(
                [device],
                mode="standard",
                exec_strategy="device_first",
                progress_callback=lambda t, p, s: None,
                stop_callback=None,
            )
            assert res is not None
            assert len(res) > 0
        finally:
            exe.stop()

    def test_basic_auth(self, mock_server, device, log):
        """Basic 认证流程"""
        device2 = DeviceInfo(
            index=1, ip="127.0.0.1", port=str(MOCK_PORT),
            username="admin", password="admin", online=True, status="在线",
            selected=True,
        )
        cfg = {
            "cgi_commands": ["param=2"],
            "config_concurrent": 5,
            "timeout": 5000,
            "auth_method": "basic",
            "verify_ssl": False,
        }
        exe = ConfigExecutor(cfg, log, use_async=True)
        try:
            res = exe.execute_batch(
                [device2],
                mode="standard",
                exec_strategy="device_first",
                progress_callback=lambda t, p, s: None,
                stop_callback=None,
            )
            assert res is not None
            assert len(res) > 0
        finally:
            exe.stop()
