# Async integration smoke test for ConfigExecutor
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.device_manager import ConfigExecutor, DeviceInfo
from utils.log_manager import LogManager

# Simple devices: use localhost or dummy IPs; set online=True to simulate
@pytest.fixture
def devices():
    dev = [
        DeviceInfo(index=0, ip='127.0.0.1', port='80', username='admin', password='admin', online=True),
        DeviceInfo(index=1, ip='127.0.0.1', port='81', username='admin', password='admin', online=True)
    ]
    for d in dev:
        d.status = '在线'
    return dev

@pytest.fixture
def config():
    return {
        'cgi_commands': ['testparam=1'],
        'config_concurrent': 5,
        'timeout': 2000,
        'auth_method': 'basic',
        'verify_ssl': False
    }

@pytest.fixture
def executor(config):
    log = LogManager()
    exe = ConfigExecutor(config, log, use_async=True)
    yield exe
    exe.stop()

class TestConfigExecutorAsync:
    """ConfigExecutor 异步测试"""
    
    def test_executor_creation(self, executor):
        """测试执行器创建"""
        assert executor is not None
        assert executor.use_async == True
    
    def test_execute_batch_returns_list(self, executor, devices):
        """测试批量执行返回列表（注意：由于没有真实设备，会连接失败）"""
        # 注意：这个测试会尝试连接，但由于没有真实设备会失败
        # 我们只验证返回类型
        result = executor.execute_batch(
            devices, 
            mode='standard', 
            exec_strategy='device_first', 
            progress_callback=lambda t,p,s: None, 
            stop_callback=None
        )
        # 应该返回一个列表（可能是空列表或错误列表）
        assert isinstance(result, list)
