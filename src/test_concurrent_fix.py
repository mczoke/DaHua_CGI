#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试并发控制优化效果
"""

import asyncio
import time
from utils.device_manager import ConfigExecutor, DeviceInfo
from utils.log_manager import LogManager

async def test_concurrent_optimization():
    """测试并发控制优化效果"""
    
    # 创建日志管理器
    log_manager = LogManager()
    
    # 创建配置
    config = {
        "config_concurrent": 30,  # 并发数
        "timeout": 3000,  # 超时时间
        "auth_method": "digest",
        "cgi_commands": [
            "Network.HTTP.Enable=false",
            "Network.HTTP.Port=80",
            "Network.RTSP.Enable=true"
        ]
    }
    
    # 创建配置执行器（启用异步模式）
    executor = ConfigExecutor(config, log_manager, use_async=True)
    
    print("=== 并发控制优化测试 ===")
    print(f"设备并发数: {executor.config_concurrent}")
    print(f"命令并发数: {executor.config_concurrent * 2}")
    print(f"连接池大小: 300")
    print(f"超时时间: {executor.timeout}秒")
    
    # 检查异步管理器是否正常初始化
    if executor.async_manager:
        print("✓ AsyncIOManager 初始化成功")
        print(f"✓ 设备级别信号量: {executor._async_semaphore._value}")
        print(f"✓ 命令级别信号量: {executor._async_command_semaphore._value}")
    else:
        print("✗ AsyncIOManager 初始化失败")
        return
    
    # 模拟大量设备
    devices = []
    for i in range(50):  # 50台设备
        device = DeviceInfo(
            index=i,
            ip=f"192.168.1.{i+100}",  # 使用不存在的IP模拟超时
            port="80",
            username="admin",
            password="12345",
            online=True,
            status="在线"
        )
        devices.append(device)
    
    print(f"\n模拟 {len(devices)} 台设备配置")
    print(f"每台设备 {len(config['cgi_commands'])} 条命令")
    print(f"总任务数: {len(devices) * len(config['cgi_commands'])}")
    
    # 测试异步配置
    start_time = time.time()
    
    try:
        # 执行批量配置（使用设备优先策略）
        results = await executor._async_execute_by_device(devices, progress_callback=None)
    
        end_time = time.time()
        execution_time = end_time - start_time
        
        print(f"\n=== 测试结果 ===")
        print(f"总执行时间: {execution_time:.2f}秒")
        
        # 统计结果
        success_count = 0
        timeout_count = 0
        error_count = 0
        
        for result in results:
            if result and 'success' in result:
                if result['success']:
                    success_count += 1
                else:
                    if "超时" in str(result.get('failure_details', '')):
                        timeout_count += 1
                    else:
                        error_count += 1
        
        print(f"成功设备: {success_count}")
        print(f"超时设备: {timeout_count}")
        print(f"错误设备: {error_count}")
        
        # 计算并发效率
        if execution_time > 0:
            total_commands = len(devices) * len(config['cgi_commands'])
            commands_per_second = total_commands / execution_time
            print(f"命令处理速度: {commands_per_second:.2f} 条/秒")
        
        # 分析并发控制效果
        print(f"\n=== 并发控制分析 ===")
        print(f"设备并发限制: {executor.config_concurrent}")
        print(f"命令并发限制: {executor.config_concurrent * 2}")
        
        if timeout_count > 0:
            timeout_rate = timeout_count / len(devices) * 100
            print(f"超时率: {timeout_rate:.1f}%")
            
            if timeout_rate > 20:
                print("⚠️  超时率较高，可能需要进一步优化")
            else:
                print("✓ 超时率在可接受范围内")
        
    except Exception as e:
        print(f"测试过程中出现异常: {e}")
    
    finally:
        # 清理资源
        executor.stop()

if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_concurrent_optimization())