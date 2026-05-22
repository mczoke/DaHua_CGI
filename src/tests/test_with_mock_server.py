import os
"""Run ConfigExecutor tests against a local mock CGI server.

This script starts the aiohttp mock server in a background thread (safe on Windows),
then runs two tests (digest and basic) against it, and finally stops the server.
"""
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time
import threading
import asyncio

sys.path.insert(0, r"C:\Users\Administrator\Desktop\CGI\V9.5")

from aiohttp import web
from src.utils.device_manager import ConfigExecutor, DeviceInfo
from src.utils.log_manager import LogManager


def start_mock_server_thread():
    """Start the mock aiohttp server in a background thread and return control handles."""
    server = {}

    def _run():
        loop = asyncio.new_event_loop()
        server['loop'] = loop
        asyncio.set_event_loop(loop)

        # import mock handler and build app
        import tests.mock_cgi_server as m
        app = web.Application()
        app.router.add_get('/cgi-bin/configManager.cgi', m.handle_config)

        runner = web.AppRunner(app)
        loop.run_until_complete(runner.setup())
        site = web.TCPSite(runner, '127.0.0.1', 8080)
        loop.run_until_complete(site.start())

        try:
            loop.run_forever()
        finally:
            loop.run_until_complete(runner.cleanup())
            loop.close()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    # wait for the server loop to be created and started
    timeout = 5
    start = time.time()
    while 'loop' not in server and time.time() - start < timeout:
        time.sleep(0.05)
    time.sleep(0.2)
    server['thread'] = t
    return server


def stop_mock_server(server):
    if not server or 'loop' not in server:
        return
    loop = server['loop']
    loop.call_soon_threadsafe(loop.stop)
    server['thread'].join(timeout=2)


if __name__ == '__main__':
    server = start_mock_server_thread()

    devices = [
        DeviceInfo(index=0, ip='127.0.0.1', port='8080', username='admin', password='admin', online=True, status='在线'),
        DeviceInfo(index=1, ip='127.0.0.1', port='8080', username='admin', password='admin', online=True, status='在线')
    ]

    log = LogManager()

    # Test Digest path
    cfg = {'cgi_commands': ['param=1'], 'config_concurrent': 5, 'timeout': 5000, 'auth_method': 'digest', 'verify_ssl': False}
    exe = ConfigExecutor(cfg, log, use_async=True)
    print('Running digest test...')
    res = exe.execute_batch(devices, mode='standard', exec_strategy='device_first', progress_callback=lambda t,p,s: print('PROG', p), stop_callback=None)
    print('Digest result:', res)
    exe.stop()

    # Test Basic path
    # reset device status to online so they are eligible again
    for d in devices:
        d.status = '在线'

    cfg2 = {'cgi_commands': ['param=2'], 'config_concurrent': 5, 'timeout': 5000, 'auth_method': 'basic', 'verify_ssl': False}
    exe2 = ConfigExecutor(cfg2, log, use_async=True)
    print('Running basic test...')
    res2 = exe2.execute_batch(devices, mode='standard', exec_strategy='device_first', progress_callback=lambda t,p,s: print('PROG', p), stop_callback=None)
    print('Basic result:', res2)
    exe2.stop()

    stop_mock_server(server)
