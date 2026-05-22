# 简单测试: 导入 AsyncIOManager 并初始化/关闭，验证没有语法错误并能启动后台 loop
from utils.async_executor import AsyncIOManager
import time

m = AsyncIOManager(timeout=5, verify_ssl=False, max_connections=10, auth_method='basic')
print('AsyncIOManager started')
# 等待短暂时间再关闭
time.sleep(1)
m.close()
print('AsyncIOManager closed')
