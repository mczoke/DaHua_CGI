#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试实际应用中的异步功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.device_manager import ConfigExecutor, DeviceInfo
from utils.log_manager import LogManager

def test_real_async():
    """测试实际应用中的异步功能"""
    print("=== 测试实际应用中的异步功能 ===")
    
    # 创建配置
    config = {
        'timeout': 5000,
        'config_concurrent': 5,
        'auth_method': 'digest',
        'verify_ssl': False,
        'cgi_commands': [
            '/cgi-bin/configManager.cgi?action=getConfig&name=General',
            '/cgi-bin/magicBox.cgi?action=getSystemInfo',
            '/cgi-bin/global.cgi?action=getCurrentTime'
        ]
    }
    
    # 创建日志管理器
    log_manager = LogManager()
    
    # 创建测试设备（使用本地回环地址）
    devices = [
        DeviceInfo(index=0, ip='127.0.0.1', port='80', username='admin', password='admin', online=True, status='在线'),
        DeviceInfo(index=1, ip='localhost', port='80', username='admin', password='admin', online=True, status='在线'),
        DeviceInfo(index=2, ip='127.0.0.2', port='80', username='admin', password='admin', online=True, status='在线')
    ]
    
    # 测试1：创建异步执行器
    print("\n1. 创建异步执行器...")
    try:
        executor = ConfigExecutor(config, log_manager, use_async=True)
        print(f"   AsyncIOManager 状态: {executor.async_manager is not None}")
        print(f"   use_async 设置: {executor.use_async}")
        
        if executor.async_manager:
            print("   ✅ 异步管理器初始化成功")
        else:
            print("   ❌ 异步管理器初始化失败，将使用同步模式")
            
    except Exception as e:
        print(f"   ❌ 创建异步执行器失败: {e}")
        return
    
    # 测试2：测试异步执行
    print("\n2. 测试异步执行...")
    try:
        # 模拟进度回调
        def progress_callback(tag, progress, stats):
            print(f"   进度: {progress:.1f}% - 完成: {stats.get('completed', 0)}/{stats.get('total', 0)}")
        
        # 执行批量配置
        results = executor.execute_batch(
            devices, 
            mode='standard', 
            exec_strategy='device_first',
            progress_callback=progress_callback
        )
        
        print(f"   执行完成，结果数量: {len(results)}")
        
        # 分析结果
        for result in results:
            device = result['device']
            print(f"   设备 {device.ip}: 成功={result['success']}, 成功命令={result['success_commands']}, 失败命令={result['failed_commands']}")
            
    except Exception as e:
        print(f"   ❌ 异步执行失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 测试3：检查异步管理器状态
    print("\n3. 检查异步管理器状态...")
    if executor.async_manager:
        print(f"   异步管理器状态: 已创建")
        print(f"   事件循环状态: {executor.async_manager.loop.is_running() if executor.async_manager.loop else '无事件循环'}")
    else:
        print("   异步管理器未创建")
    
    # 清理
    print("\n4. 清理资源...")
    try:
        executor.stop()
        print("   执行器已停止")
    except Exception as e:
        print(f"   停止执行器失败: {e}")

if __name__ == '__main__':
    test_real_async()