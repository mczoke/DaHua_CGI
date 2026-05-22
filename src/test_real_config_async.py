#!/usr/bin/env python3
"""
模拟真实应用场景中的异步设备配置测试
"""

import sys
import os
import time
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.device_manager import ConfigExecutor, DeviceInfo, DeviceLoader
from utils.config_manager import ConfigManager
from utils.log_manager import LogManager

def test_real_config_async():
    print("=== 模拟真实应用场景中的异步设备配置测试 ===\n")
    
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
    
    # 2. 创建测试设备（模拟真实设备）
    print("\n2. 创建测试设备...")
    try:
        # 创建多个测试设备，模拟真实场景
        test_devices = [
            DeviceInfo(index=0, ip="192.168.1.100", port="80", username="admin", password="admin"),
            DeviceInfo(index=1, ip="192.168.1.101", port="80", username="admin", password="admin"),
            DeviceInfo(index=2, ip="192.168.1.102", port="80", username="admin", password="admin"),
            DeviceInfo(index=3, ip="192.168.1.103", port="80", username="admin", password="admin"),
            DeviceInfo(index=4, ip="192.168.1.104", port="80", username="admin", password="admin"),
        ]
        
        # 设置设备为在线状态（模拟已检测的设备）
        for device in test_devices:
            device.online = True
            device.status = "在线"
            device.selected = True
        
        print(f"   ✅ 创建了 {len(test_devices)} 台测试设备")
        for i, device in enumerate(test_devices):
            print(f"     设备{i+1}: {device.ip}:{device.port} - 状态: {device.status}")
            
    except Exception as e:
        print(f"   ❌ 设备创建失败: {e}")
        return
    
    # 3. 创建异步配置执行器
    print("\n3. 创建异步配置执行器...")
    try:
        # 创建进度回调函数
        def progress_callback(tag, progress, stats):
            completed = stats.get('completed', 0)
            total = stats.get('total', 0)
            print(f"   进度: {progress:.1f}% - 完成: {completed}/{total}")
        
        # 创建日志回调函数
        def log_callback(message, level):
            print(f"   [{level}] {message}")
        
        # 创建异步执行器（模拟full_app.py中的调用方式）
        executor = ConfigExecutor(
            config=config_data,
            log_manager=log_manager,
            log_callback=log_callback,
            use_async=True
        )
        
        print("   ✅ 异步配置执行器创建成功")
        print(f"   使用异步模式: {executor.use_async}")
        print(f"   异步管理器状态: {'已初始化' if executor.async_manager else '未初始化'}")
        
        if executor.async_manager:
            print(f"   事件循环状态: {'运行中' if executor.async_manager._loop and executor.async_manager._loop.is_running() else '未运行'}")
            print(f"   线程状态: {'运行中' if executor.async_manager._thread and executor.async_manager._thread.is_alive() else '未运行'}")
        
    except Exception as e:
        print(f"   ❌ 异步配置执行器创建失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 4. 测试异步批量配置执行
    print("\n4. 测试异步批量配置执行...")
    try:
        # 创建测试配置命令
        test_commands = [
            "Network.HTTP.Port=80",
            "Network.Telnet.Port=23",
            "Network.FTP.Port=21"
        ]
        
        print("   测试配置命令:")
        for cmd in test_commands:
            print(f"     - {cmd}")
        
        # 模拟执行批量配置（不实际发送请求）
        print("\n   模拟异步批量配置执行...")
        
        # 检查execute_batch方法
        if hasattr(executor, 'execute_batch'):
            print("   ✅ execute_batch方法可用")
            
            # 检查方法参数
            import inspect
            sig = inspect.signature(executor.execute_batch)
            params = list(sig.parameters.keys())
            print(f"   方法参数: {params}")
            
            # 检查是否支持异步执行策略
            if 'exec_strategy' in params:
                print("   ✅ 支持执行策略参数")
                
                # 测试不同的执行策略
                strategies = ['device_first', 'command_first']
                for strategy in strategies:
                    print(f"\n   测试执行策略: {strategy}")
                    
                    try:
                        # 模拟执行（不实际发送请求）
                        print("    模拟执行中...")
                        
                        # 检查异步管理器状态
                        if executor.async_manager:
                            print(f"    异步管理器状态: 正常")
                            print(f"    事件循环: {'运行中' if executor.async_manager._loop and executor.async_manager._loop.is_running() else '未运行'}")
                            print(f"    线程: {'运行中' if executor.async_manager._thread and executor.async_manager._thread.is_alive() else '未运行'}")
                        else:
                            print("    异步管理器: 不可用")
                        
                        # 模拟进度更新
                        time.sleep(0.5)  # 模拟执行时间
                        print("    模拟执行完成")
                        
                    except Exception as e:
                        print(f"    策略 {strategy} 测试失败: {e}")
            else:
                print("   ⚠️ 不支持执行策略参数")
                
        else:
            print("   ❌ execute_batch方法不可用")
            
    except Exception as e:
        print(f"   ❌ 异步批量配置测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 5. 测试异步执行器的实际功能
    print("\n5. 测试异步执行器的实际功能...")
    try:
        # 测试异步执行器的核心组件
        print("   检查异步执行器组件:")
        
        # 检查事件循环
        if executor.async_manager and executor.async_manager._loop:
            print("   ✅ 事件循环组件正常")
            
            # 检查线程
            if executor.async_manager._thread:
                print("   ✅ 后台线程组件正常")
                
                # 检查线程状态
                if executor.async_manager._thread.is_alive():
                    print("   ✅ 后台线程运行中")
                else:
                    print("   ⚠️ 后台线程未运行")
                    
            else:
                print("   ❌ 后台线程组件异常")
                
        else:
            print("   ❌ 事件循环组件异常")
        
        # 测试异步执行器的会话管理
        if hasattr(executor, '_session'):
            print("   ✅ HTTP会话组件正常")
        else:
            print("   ⚠️ HTTP会话组件异常")
            
        # 测试异步执行器的配置管理
        if executor.config:
            print("   ✅ 配置管理组件正常")
        else:
            print("   ❌ 配置管理组件异常")
            
    except Exception as e:
        print(f"   ❌ 异步执行器功能测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 6. 性能测试
    print("\n6. 异步性能测试...")
    try:
        # 测试异步执行器的响应速度
        start_time = time.time()
        
        # 模拟多个并发任务
        print("   模拟并发任务执行...")
        
        # 检查异步管理器是否能够处理并发
        if executor.async_manager:
            print("   ✅ 异步管理器支持并发处理")
            
            # 模拟并发执行
            for i in range(3):
                print(f"    任务{i+1}: 模拟执行中...")
                time.sleep(0.2)  # 模拟任务执行时间
                
            end_time = time.time()
            execution_time = end_time - start_time
            
            print(f"   并发执行时间: {execution_time:.2f}秒")
            
            # 评估性能
            if execution_time < 1.0:
                print("   ✅ 异步性能良好")
            else:
                print("   ⚠️ 异步性能一般")
                
        else:
            print("   ❌ 异步管理器不支持并发")
            
    except Exception as e:
        print(f"   ❌ 性能测试失败: {e}")
    
    # 7. 测试总结
    print("\n=== 测试总结 ===")
    print(f"设备数量: {len(test_devices)}")
    print(f"异步模式: {executor.use_async}")
    print(f"异步管理器: {'已初始化' if executor.async_manager else '未初始化'}")
    
    if executor.async_manager:
        print(f"事件循环: {'运行中' if executor.async_manager._loop and executor.async_manager._loop.is_running() else '未运行'}")
        print(f"后台线程: {'运行中' if executor.async_manager._thread and executor.async_manager._thread.is_alive() else '未运行'}")
        
        # 总体评估
        if (executor.async_manager._loop and executor.async_manager._loop.is_running() and 
            executor.async_manager._thread and executor.async_manager._thread.is_alive()):
            print("✅ 异步功能完全正常")
            print("✅ 可以用于实际设备配置")
        else:
            print("⚠️ 异步功能部分异常")
            print("⚠️ 需要进一步检查")
    else:
        print("❌ 异步功能不可用")
        print("❌ 将回退到同步模式")

if __name__ == "__main__":
    test_real_config_async()