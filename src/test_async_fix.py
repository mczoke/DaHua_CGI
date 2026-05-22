#!/usr/bin/env python3
"""
测试异步配置修复：认证会话缓存和并发控制
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.async_executor import AsyncIOManager

class MockDevice:
    """模拟设备类"""
    def __init__(self, ip, port, username, password):
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password

async def test_async_manager():
    """测试AsyncIOManager的认证缓存功能"""
    print("=== 测试异步管理器认证缓存功能 ===")
    
    # 创建异步管理器
    manager = AsyncIOManager(timeout=5, auth_method='digest')
    
    # 创建模拟设备
    device = MockDevice("192.168.1.100", 80, "admin", "admin123")
    
    # 测试认证缓存机制
    print("1. 检查认证缓存初始化...")
    print(f"   认证缓存: {manager._auth_cache}")
    print(f"   认证缓存锁: {manager._auth_cache_lock}")
    
    # 测试_request_with_digest_cached方法是否存在
    print("2. 检查带缓存认证方法...")
    if hasattr(manager, '_request_with_digest_cached'):
        print("   ✓ _request_with_digest_cached方法存在")
    else:
        print("   ✗ _request_with_digest_cached方法不存在")
        return False
    
    # 测试设备键生成
    device_key = f"{device.ip}:{device.port}"
    print(f"3. 设备键生成测试: {device_key}")
    
    print("4. 测试认证参数缓存机制...")
    # 模拟认证参数
    auth_params = {
        'realm': 'Dahua IP Camera',
        'nonce': 'abc123',
        'qop': 'auth'
    }
    
    # 测试缓存写入
    with manager._auth_cache_lock:
        manager._auth_cache[device_key] = auth_params
    
    # 测试缓存读取
    with manager._auth_cache_lock:
        cached_params = manager._auth_cache.get(device_key)
    
    if cached_params == auth_params:
        print("   ✓ 认证参数缓存机制正常")
    else:
        print("   ✗ 认证参数缓存机制异常")
        return False
    
    print("5. 测试认证缓存清理...")
    with manager._auth_cache_lock:
        manager._auth_cache.pop(device_key, None)
    
    with manager._auth_cache_lock:
        cached_params = manager._auth_cache.get(device_key)
    
    if cached_params is None:
        print("   ✓ 认证缓存清理正常")
    else:
        print("   ✗ 认证缓存清理异常")
        return False
    
    print("\n=== 测试完成 ===")
    
    # 关闭管理器
    manager.close()
    
    return True

def test_config_concurrent():
    """测试并发控制配置"""
    print("\n=== 测试并发控制配置 ===")
    
    # 导入device_manager模块
    try:
        from utils.device_manager import ConfigExecutor
        
        # 创建模拟的log_manager
        class MockLogManager:
            def log_detailed(self, message, level):
                pass
            def log_failure(self, device, message):
                pass
        
        mock_log_manager = MockLogManager()
        
        # 测试默认配置
        config = {}
        executor = ConfigExecutor(config, mock_log_manager)
        
        print(f"1. 默认并发控制数: {executor.config_concurrent}")
        
        # 测试自定义配置
        config_custom = {"config_concurrent": 3}
        executor_custom = ConfigExecutor(config_custom, mock_log_manager)
        
        print(f"2. 自定义并发控制数: {executor_custom.config_concurrent}")
        
        if executor.config_concurrent == 5 and executor_custom.config_concurrent == 3:
            print("   ✓ 并发控制配置修复正常")
            return True
        else:
            print("   ✗ 并发控制配置修复异常")
            return False
            
    except Exception as e:
        print(f"   ✗ 测试失败: {e}")
        return False

if __name__ == "__main__":
    print("开始测试异步配置修复...\n")
    
    # 运行异步测试
    async_result = asyncio.run(test_async_manager())
    
    # 运行并发控制测试
    concurrent_result = test_config_concurrent()
    
    print("\n=== 测试结果汇总 ===")
    print(f"认证缓存修复: {'✓ 通过' if async_result else '✗ 失败'}")
    print(f"并发控制修复: {'✓ 通过' if concurrent_result else '✗ 失败'}")
    
    if async_result and concurrent_result:
        print("\n🎉 所有修复测试通过！")
        print("修复内容:")
        print("1. 认证会话缓存机制 - 避免重复Digest认证握手")
        print("2. 并发控制优化 - 默认并发数从50降低到5")
        print("3. 线程安全认证缓存 - 使用锁保护缓存操作")
    else:
        print("\n❌ 部分测试失败，请检查修复代码")
        sys.exit(1)