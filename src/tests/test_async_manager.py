"""测试 AsyncIOManager 初始化和关闭"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.async_executor import AsyncIOManager


class TestAsyncIOManager:
    """验证 AsyncIOManager 能正常启动和关闭"""

    def test_init_basic(self):
        """basic 认证模式初始化"""
        m = AsyncIOManager(timeout=5, verify_ssl=False, max_connections=10, auth_method='basic')
        assert m is not None
        assert m._closed is False
        assert m.timeout == 5
        assert m.auth_method == 'basic'
        m.close()
        assert m._closed is True

    def test_init_digest(self):
        """digest 认证模式初始化"""
        m = AsyncIOManager(timeout=10, verify_ssl=False, max_connections=5, auth_method='digest')
        assert m is not None
        assert m._closed is False
        assert m.auth_method == 'digest'
        assert m.max_connections == 5
        m.close()
        assert m._closed is True

    def test_close_twice_no_error(self):
        """重复 close 不报错"""
        m = AsyncIOManager(timeout=3, verify_ssl=False)
        m.close()
        m.close()  # 第二次不应异常
        assert m._closed is True

    def test_default_params(self):
        """默认参数初始化"""
        m = AsyncIOManager()
        assert m.timeout == 30
        assert m.verify_ssl is True
        assert m.max_connections == 100
        assert m.auth_method == 'digest'
        m.close()
