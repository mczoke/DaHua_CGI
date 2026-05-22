#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
URL认证功能测试脚本
测试异步设备优先模式下的URL认证功能
"""

import sys
import os
import asyncio
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.device_manager import ConfigExecutor
from utils.log_manager import LogManager

class MockDevice:
    """模拟设备类"""
    def __init__(self, ip, port=80, username="admin", password="admin"):
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.online = True
        self.status = "在线"
        self.last_message = ""
        self.index = 0
        self.variables = {}
        self.selected = True  # 添加selected属性

class MockLogManager:
    """模拟日志管理器"""
    def log_detailed(self, message, level="INFO"):
        print(f"[{level}] {message}")
    
    def log_cgi_request(self, ip, cmd_index, total_commands, url, auth_method, headers, raw_command=None):
        print(f"[CGI请求] {ip} 命令{cmd_index}/{total_commands}: {url}")
    
    def log_cgi_response(self, ip, status_code, request_time, headers, body, success=True, raw_command=None):
        status = "成功" if success else "失败"
        print(f"[CGI响应] {ip} 状态码={status_code}, 耗时={request_time:.2f}s, {status}")
    
    def log_failure(self, device, message, command=None):
        print(f"[失败] {device.ip}: {message}")

async def test_url_auth():
    """测试URL认证功能"""
    print("=== URL认证功能测试 ===")
    
    # 创建配置
    config = {
        "config_concurrent": 3,  # 并发数
        "timeout": 5000,  # 超时时间
        "auth_method": "digest",  # 认证方式
        "cgi_commands": [
            "VideoWidget[0].CustomTitle[1]=测试标题",
            "VideoColor[0].Brightness=50",
            "VideoColor[0].Contrast=50"
        ]
    }
    
    # 创建日志管理器
    log_manager = MockLogManager()
    
    # 创建配置执行器（启用异步模式）
    executor = ConfigExecutor(config, log_manager, use_async=True)
    
    # 创建测试设备
    test_devices = [
        MockDevice("192.168.1.100", 80, "admin", "admin"),
        MockDevice("192.168.1.101", 80, "admin", "admin123"),
        MockDevice("192.168.1.102", 80, "admin", "password")
    ]
    
    print(f"测试设备数量: {len(test_devices)}")
    print(f"测试命令数量: {len(config['cgi_commands'])}")
    print(f"并发控制数: {config['config_concurrent']}")
    print()
    
    # 测试设备优先模式
    print("=== 测试设备优先模式 ===")
    
    def progress_callback(phase, progress, stats):
        print(f"进度: {phase} {progress:.1f}% - 完成: {stats['completed']}/{stats['total']} "
              f"成功: {stats['success']} 失败: {stats['failed']}")
    
    try:
        # 使用AsyncIOManager的run_coroutine方法执行异步设备优先配置
        future = executor.async_manager.run_coroutine(
            executor._async_execute_by_device(
                test_devices, 
                mode="standard", 
                progress_callback=progress_callback
            )
        )
        results = future.result()
        
        print("\n=== 测试结果汇总 ===")
        for result in results:
            device = result['device']
            print(f"设备 {device.ip}: {device.status} - {device.last_message}")
            print(f"  命令执行: {result['success_commands']}/{result['total_commands']} 成功")
            if result['failure_details']:
                print(f"  失败详情: {result['failure_details']}")
            print()
        
        # 统计总体结果
        total_success = sum(r['success_commands'] for r in results)
        total_failed = sum(r['failed_commands'] for r in results)
        total_commands = sum(r['total_commands'] for r in results)
        
        print(f"总体结果: {total_success}/{total_commands} 命令成功执行")
        print(f"成功率: {total_success/total_commands*100:.1f}%")
        
        return total_success > 0  # 只要有一个命令成功就认为测试通过
        
    except Exception as e:
        print(f"测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_single_command():
    """测试单个命令的URL认证"""
    print("\n=== 测试单个命令URL认证 ===")
    
    # 创建配置
    config = {
        "timeout": 5000,
        "auth_method": "digest"
    }
    
    # 创建日志管理器
    log_manager = MockLogManager()
    
    # 创建配置执行器
    executor = ConfigExecutor(config, log_manager, use_async=True)
    
    # 创建测试设备
    device = MockDevice("192.168.1.100", 80, "admin", "admin")
    
    try:
        # 使用AsyncIOManager的run_coroutine方法测试URL认证发送命令
        future = executor.async_manager.run_coroutine(
            executor._async_send_command_with_url_auth(
                device, "VideoWidget[0].CustomTitle[1]=测试标题", 1, 1
            )
        )
        success, message = future.result()
        
        print(f"单个命令测试结果: {'成功' if success else '失败'} - {message}")
        return success
        
    except Exception as e:
        print(f"单个命令测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """主测试函数"""
    print("开始URL认证功能测试...")
    
    # 测试单个命令
    single_test_result = test_single_command()
    
    # 测试设备优先模式
    device_test_result = await test_url_auth()
    
    print("\n=== 最终测试结果 ===")
    print(f"单个命令测试: {'通过' if single_test_result else '失败'}")
    print(f"设备优先模式测试: {'通过' if device_test_result else '失败'}")
    
    if single_test_result and device_test_result:
        print("\n✅ 所有URL认证测试通过！")
        return True
    else:
        print("\n❌ 部分测试失败，请检查代码实现")
        return False

if __name__ == "__main__":
    # 运行测试
    result = asyncio.run(main())
    sys.exit(0 if result else 1)