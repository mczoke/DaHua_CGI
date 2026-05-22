# Async integration smoke test for ConfigExecutor
import sys
sys.path.insert(0, r"C:\Users\Administrator\Desktop\CGI\V9.5")
from utils.device_manager import ConfigExecutor, DeviceInfo
from utils.log_manager import LogManager

# Simple devices: use localhost or dummy IPs; set online=True to simulate
devices = [
    DeviceInfo(index=0, ip='127.0.0.1', port='80', username='admin', password='admin', online=True),
    DeviceInfo(index=1, ip='127.0.0.1', port='81', username='admin', password='admin', online=True)
]
# 标记为在线以满足严格筛选条件
for d in devices:
    d.status = '在线'

log = LogManager()
config = {
    'cgi_commands': ['testparam=1'],
    'config_concurrent': 5,
    'timeout': 2000,
    'auth_method': 'basic',
    'verify_ssl': False
}

exe = ConfigExecutor(config, log, use_async=True)
print('Executor created, use_async=', exe.use_async)

res = exe.execute_batch(devices, mode='standard', exec_strategy='device_first', progress_callback=lambda t,p,s: print('PROG',p), stop_callback=None)
print('execute_batch returned:', res)
exe.stop()
print('Stopped')
