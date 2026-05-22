#!/usr/bin/env python3
"""
检查实际应用中ConfigExecutor的异步功能状态
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.device_manager import ConfigExecutor, DeviceInfo
from utils.async_executor import AsyncIOManager

def check_real_async_usage():
    print("=== 检查实际应用中ConfigExecutor的异步功能状态 ===\n")
    
    # 1. 检查AsyncIOManager是否可用
    print("1. 检查AsyncIOManager可用性...")
    try:
        async_manager = AsyncIOManager(timeout=10, verify_ssl=False, max_connections=50)
        print("   ✅ AsyncIOManager可用")
        print(f"   事件循环状态: {'运行中' if async_manager._loop and async_manager._loop.is_running() else '未运行'}")
        print(f"   线程状态: {'运行中' if async_manager._thread and async_manager._thread.is_alive() else '未运行'}")
    except Exception as e:
        print(f"   ❌ AsyncIOManager不可用: {e}")
        return
    
    # 2. 检查ConfigExecutor异步模式
    print("\n2. 检查ConfigExecutor异步模式...")
    try:
        # 创建一个测试设备
        test_device = DeviceInfo(
            index=0,
            ip="192.168.1.100",
            port="80",
            username="admin",
            password="admin"
        )
        
        # 创建异步模式的ConfigExecutor
        executor = ConfigExecutor(
            devices=[test_device],
            config_commands=["Network.HTTP.Port=80"],
            use_async=True,
            timeout=10,
            verify_ssl=False,
            max_connections=50
        )
        
        print("   ✅ ConfigExecutor异步模式创建成功")
        print(f"   异步管理器状态: {'已初始化' if executor.async_manager else '未初始化'}")
        print(f"   使用异步模式: {executor.use_async}")
        
        if executor.async_manager:
            print(f"   异步管理器事件循环: {'运行中' if executor.async_manager._loop and executor.async_manager._loop.is_running() else '未运行'}")
        else:
            print("   ⚠️ 异步管理器未初始化，将回退到同步模式")
            
    except Exception as e:
        print(f"   ❌ ConfigExecutor异步模式检查失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 3. 检查实际应用中的调用方式
    print("\n3. 检查实际应用中的调用方式...")
    try:
        # 模拟full_app.py中的调用方式
        from utils.device_manager import ConfigExecutor, DeviceInfo
        
        # 创建测试设备列表
        test_devices = [
            DeviceInfo(index=0, ip="192.168.1.101", port="80", username="admin", password="admin"),
            DeviceInfo(index=1, ip="192.168.1.102", port="80", username="admin", password="admin"),
        ]
        
        # 创建配置命令
        config_commands = [
            "Network.HTTP.Port=80",
            "Network.FTP.Enable=false"
        ]
        
        # 创建异步执行器
        executor = ConfigExecutor(
            devices=test_devices,
            config_commands=config_commands,
            use_async=True,
            timeout=10,
            verify_ssl=False,
            max_connections=50
        )
        
        print("   ✅ 实际应用调用方式检查成功")
        print(f"   设备数量: {len(executor.devices)}")
        print(f"   配置命令数量: {len(executor.config_commands)}")
        print(f"   异步模式: {executor.use_async}")
        print(f"   异步管理器: {'已初始化' if executor.async_manager else '未初始化'}")
        
        # 检查execute_batch方法
        print("\n4. 检查execute_batch方法...")
        try:
            # 创建一个简单的进度回调
            def progress_callback(device, command, status, message, progress):
                print(f"   进度回调: {device.ip} - {command} - {status} - {message} - {progress}%")
            
            # 尝试执行（不实际发送请求）
            print("   模拟执行execute_batch...")
            
            # 检查方法是否存在
            if hasattr(executor, 'execute_batch'):
                print("   ✅ execute_batch方法存在")
                
                # 检查方法签名
                import inspect
                sig = inspect.signature(executor.execute_batch)
                print(f"   方法参数: {list(sig.parameters.keys())}")
                
                # 检查是否支持异步
                if 'use_async' in sig.parameters:
                    print("   ✅ execute_batch支持use_async参数")
                else:
                    print("   ⚠️ execute_batch不支持use_async参数")
                    
            else:
                print("   ❌ execute_batch方法不存在")
                
        except Exception as e:
            print(f"   ❌ execute_batch检查失败: {e}")
            
    except Exception as e:
        print(f"   ❌ 实际应用调用方式检查失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n=== 诊断完成 ===")

if __name__ == "__main__":
    check_real_async_usage()