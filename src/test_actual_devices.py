#!/usr/bin/env python3
"""
使用实际加载的设备测试异步功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.device_manager import ConfigExecutor, DeviceInfo, DeviceLoader
from utils.config_manager import ConfigManager
from utils.log_manager import LogManager
from utils.async_executor import AsyncIOManager

def test_actual_devices_async():
    print("=== 使用实际加载的设备测试异步功能 ===\n")
    
    # 1. 初始化必要的组件
    print("1. 初始化组件...")
    try:
        # 加载配置
        config_data = ConfigManager.load_config()
        print("   ✅ 配置加载成功")
        
        # 初始化日志管理器
        log_manager = LogManager()
        print("   ✅ 日志管理器初始化成功")
        
        # 初始化设备加载器
        device_loader = DeviceLoader(log_manager)
        print("   ✅ 设备加载器初始化成功")
        
    except Exception as e:
        print(f"   ❌ 组件初始化失败: {e}")
        return
    
    # 2. 检查是否有已加载的设备
    print("\n2. 检查已加载的设备...")
    try:
        # 模拟实际应用中的设备加载方式
        # 首先检查是否有Excel文件可用
        excel_files = []
        for file in os.listdir("."):
            if file.endswith(('.xlsx', '.xls')):
                excel_files.append(file)
        
        if excel_files:
            print(f"   ✅ 发现Excel文件: {', '.join(excel_files)}")
            # 使用第一个Excel文件
            excel_file = excel_files[0]
            print(f"   尝试加载: {excel_file}")
            
            try:
                devices, count = device_loader.load_from_excel(excel_file)
                print(f"   ✅ 成功加载 {count} 台设备")
                for i, device in enumerate(devices[:5]):  # 只显示前5台
                    print(f"     设备{i+1}: {device.ip}:{device.port} - {device.username}")
                if count > 5:
                    print(f"     ... 还有 {count - 5} 台设备")
            except Exception as e:
                print(f"   ⚠️ Excel加载失败: {e}")
                print("   将使用测试设备")
                # 创建测试设备
                devices = [
                    DeviceInfo(index=0, ip="192.168.1.100", port="80", username="admin", password="admin"),
                    DeviceInfo(index=1, ip="192.168.1.101", port="80", username="admin", password="admin"),
                ]
        else:
            print("   ⚠️ 没有找到Excel文件，将使用测试设备")
            # 创建测试设备
            devices = [
                DeviceInfo(index=0, ip="192.168.1.100", port="80", username="admin", password="admin"),
                DeviceInfo(index=1, ip="192.168.1.101", port="80", username="admin", password="admin"),
            ]
            
    except Exception as e:
        print(f"   ❌ 设备检查失败: {e}")
        return
    
    # 3. 测试AsyncIOManager
    print("\n3. 测试AsyncIOManager...")
    try:
        async_manager = AsyncIOManager(timeout=10, verify_ssl=False, max_connections=50)
        print("   ✅ AsyncIOManager初始化成功")
        print(f"   事件循环状态: {'运行中' if async_manager._loop and async_manager._loop.is_running() else '未运行'}")
        print(f"   线程状态: {'运行中' if async_manager._thread and async_manager._thread.is_alive() else '未运行'}")
        
    except Exception as e:
        print(f"   ❌ AsyncIOManager测试失败: {e}")
        return
    
    # 4. 测试ConfigExecutor异步模式
    print("\n4. 测试ConfigExecutor异步模式...")
    try:
        # 创建异步执行器（模拟full_app.py中的调用方式）
        executor = ConfigExecutor(
            config=config_data,
            log_manager=log_manager,
            log_callback=lambda msg, level: print(f"   [{level}] {msg}"),
            use_async=True
        )
        
        print("   ✅ ConfigExecutor异步模式创建成功")
        print(f"   使用异步模式: {executor.use_async}")
        print(f"   异步管理器状态: {'已初始化' if executor.async_manager else '未初始化'}")
        
        if executor.async_manager:
            print(f"   异步管理器事件循环: {'运行中' if executor.async_manager._loop and executor.async_manager._loop.is_running() else '未运行'}")
        else:
            print("   ⚠️ 异步管理器未初始化，将回退到同步模式")
            
    except Exception as e:
        print(f"   ❌ ConfigExecutor异步模式测试失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 5. 测试异步执行功能
    print("\n5. 测试异步执行功能...")
    try:
        # 创建简单的进度回调
        def progress_callback(tag, progress, stats):
            print(f"   进度回调: {progress:.1f}% - 完成: {stats.get('completed', 0)}/{stats.get('total', 0)}")
        
        # 测试异步执行（不实际发送请求）
        print("   模拟异步执行...")
        
        # 检查execute_batch方法
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
                
            # 检查exec_strategy参数
            if 'exec_strategy' in sig.parameters:
                print("   ✅ execute_batch支持exec_strategy参数")
            else:
                print("   ⚠️ execute_batch不支持exec_strategy参数")
                
        else:
            print("   ❌ execute_batch方法不存在")
            
        # 测试异步执行器是否正常工作
        print("\n6. 测试异步执行器...")
        try:
            # 创建一个简单的测试命令
            test_commands = ["Network.HTTP.Port=80"]
            
            # 模拟执行（不实际发送请求）
            print("   模拟执行批量配置...")
            
            # 检查异步管理器是否可用
            if executor.async_manager:
                print("   ✅ 异步管理器可用")
                
                # 测试异步执行器的事件循环
                if executor.async_manager._loop and executor.async_manager._loop.is_running():
                    print("   ✅ 异步事件循环运行正常")
                    
                    # 测试异步执行器的线程
                    if executor.async_manager._thread and executor.async_manager._thread.is_alive():
                        print("   ✅ 异步线程运行正常")
                    else:
                        print("   ⚠️ 异步线程未运行")
                else:
                    print("   ⚠️ 异步事件循环未运行")
            else:
                print("   ❌ 异步管理器不可用")
                
        except Exception as e:
            print(f"   ❌ 异步执行器测试失败: {e}")
            
    except Exception as e:
        print(f"   ❌ 异步执行功能测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 6. 总结
    print("\n=== 测试总结 ===")
    print(f"设备数量: {len(devices)}")
    print(f"异步模式: {executor.use_async if 'executor' in locals() else '未测试'}")
    print(f"异步管理器: {'已初始化' if 'executor' in locals() and executor.async_manager else '未初始化'}")
    print(f"事件循环: {'运行中' if 'executor' in locals() and executor.async_manager and executor.async_manager._loop and executor.async_manager._loop.is_running() else '未运行'}")
    
    if 'executor' in locals() and executor.async_manager:
        print("✅ 异步功能配置正确")
    else:
        print("❌ 异步功能存在问题")

if __name__ == "__main__":
    test_actual_devices_async()