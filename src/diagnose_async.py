#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
诊断实际应用中的异步功能问题
"""

import sys
import os
import traceback
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.device_manager import ConfigExecutor, DeviceInfo
from utils.log_manager import LogManager

def diagnose_async_issue():
    """诊断异步功能问题"""
    print("=== 诊断异步功能问题 ===\n")
    
    # 创建配置
    config = {
        'timeout': 5000,
        'config_concurrent': 5,
        'auth_method': 'digest',
        'verify_ssl': False,
        'cgi_commands': [
            '/cgi-bin/configManager.cgi?action=getConfig&name=General'
        ]
    }
    
    # 创建日志管理器
    log_manager = LogManager()
    
    # 创建测试设备
    devices = [
        DeviceInfo(index=0, ip='127.0.0.1', port='80', username='admin', password='admin', online=True, status='在线')
    ]
    
    print("1. 测试AsyncIOManager导入...")
    try:
        from utils.async_executor import AsyncIOManager
        print("   ✅ AsyncIOManager导入成功")
    except Exception as e:
        print(f"   ❌ AsyncIOManager导入失败: {e}")
        traceback.print_exc()
        return
    
    print("\n2. 测试AsyncIOManager初始化...")
    try:
        async_manager = AsyncIOManager(timeout=5.0, verify_ssl=False, max_connections=100, auth_method='digest')
        print("   ✅ AsyncIOManager初始化成功")
        
        # 测试异步功能 - 使用正确的属性名
        print(f"   事件循环状态: {'运行中' if async_manager._loop and async_manager._loop.is_running() else '未运行'}")
        print(f"   线程状态: {'运行中' if async_manager._thread and async_manager._thread.is_alive() else '未运行'}")
        
        # 测试异步功能
        print("\n3. 测试异步功能...")
        import asyncio
        
        async def test_async():
            return "异步测试成功"
        
        future = async_manager.run_coroutine(test_async())
        result = future.result(timeout=5)
        print(f"   ✅ 异步功能测试成功: {result}")
        
        # 清理
        async_manager.close()
        print("   ✅ AsyncIOManager清理成功")
        
    except Exception as e:
        print(f"   ❌ AsyncIOManager初始化或测试失败: {e}")
        traceback.print_exc()
        return
    
    print("\n4. 测试ConfigExecutor异步模式...")
    try:
        executor = ConfigExecutor(config, log_manager, use_async=True)
        print(f"   ✅ ConfigExecutor创建成功")
        print(f"   use_async设置: {executor.use_async}")
        print(f"   async_manager状态: {executor.async_manager is not None}")
        
        if executor.async_manager:
            print("   ✅ 异步模式已启用")
        else:
            print("   ❌ 异步模式未启用，将使用同步模式")
            
        # 测试执行
        print("\n5. 测试批量执行...")
        def progress_callback(tag, progress, stats):
            print(f"   进度回调: {progress:.1f}%")
        
        results = executor.execute_batch(
            devices, 
            mode='standard', 
            exec_strategy='device_first',
            progress_callback=progress_callback
        )
        
        print(f"   执行完成，结果数量: {len(results)}")
        
        # 清理
        executor.stop()
        print("   ✅ 执行器清理成功")
        
    except Exception as e:
        print(f"   ❌ ConfigExecutor测试失败: {e}")
        traceback.print_exc()
    
    print("\n=== 诊断完成 ===")

if __name__ == '__main__':
    diagnose_async_issue()