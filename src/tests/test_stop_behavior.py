"""测试停止行为：启动 mock CGI server，启动执行器并在短暂等待后触发 stop，验证 AsyncIOManager 关闭。"""
import time
import threading
import sys
sys.path.insert(0, r"C:\Users\Administrator\Desktop\CGI\V9.5")

from utils.device_manager import ConfigExecutor, DeviceInfo
from utils.log_manager import LogManager
import tests.test_with_mock_server as tw


def run_executor_and_stop():
    server = tw.start_mock_server_thread()
    try:
        devices = [
            DeviceInfo(index=i, ip='127.0.0.1', port='8080', username='admin', password='admin', online=True, status='在线')
            for i in range(2)
        ]

        # 使用大量命令以保证任务运行时间足够长，便于测试停止
        cfg = {'cgi_commands': [f'param={i}' for i in range(100)], 'config_concurrent': 10, 'timeout': 5000, 'auth_method': 'digest', 'verify_ssl': False}
        log = LogManager()
        exe = ConfigExecutor(cfg, log, use_async=True)

        # 在后台线程运行 execute_batch
        result_container = {}

        def _run():
            try:
                res = exe.execute_batch(devices, mode='standard', exec_strategy='device_first', progress_callback=lambda t,p,s: print('PROG', int(p)), stop_callback=None)
                result_container['res'] = res
            except Exception as e:
                result_container['err'] = str(e)

        t = threading.Thread(target=_run, daemon=True)
        t.start()

        # 等待短暂时间后触发停止
        time.sleep(0.5)
        print('请求停止')
        exe.stop()

        # 等待线程结束
        t.join(timeout=5)

        print('后台线程是否存活:', t.is_alive())
        print('执行器停止标志:', exe._is_stopped())
        if exe.async_manager:
            print('Async manager loop:', exe.async_manager._loop)
            print('Async manager thread:', exe.async_manager._thread)
        else:
            print('无 async_manager（回退到同步或已关闭）')

        print('结果容器:', result_container)
    finally:
        tw.stop_mock_server(server)


if __name__ == '__main__':
    run_executor_and_stop()
