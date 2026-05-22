#!/usr/bin/env python3
"""
测试异步执行器日志记录修复
"""

import asyncio
import sys
import os

# 添加utils目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))

from utils.async_executor import AsyncIOManager
from utils.log_manager import LogManager

async def test_async_logging():
    """测试异步执行器的日志记录功能"""
    print("=== 测试异步执行器日志记录修复 ===")
    
    # 创建日志管理器
    log_manager = LogManager()
    
    # 创建异步管理器
    async_manager = AsyncIOManager(timeout=5, auth_method='basic')
    
    try:
        # 测试异步执行器返回值的格式
        print("1. 测试异步执行器返回值格式...")
        
        # 创建一个模拟设备对象
        class MockDevice:
            def __init__(self):
                self.index = 0
                self.ip = "192.168.1.100"
                self.port = 80
                self.username = "admin"
                self.password = "admin"
                self.online = True
                self.status = "在线"
                self.last_message = ""
                self.selected = True
                self.variables = {}
                self.result = None
                self.excel_row = 0
        
        device = MockDevice()
        # 使用一个简单的getCurrentTime命令，避免网络请求
        command_dict = {
            "action": "getCurrentTime"
        }
        
        # 测试异步执行器方法
        print("2. 测试send_command_async方法...")
        result = await async_manager.send_command_async(device, command_dict)
        
        print(f"返回值长度: {len(result)}")
        print(f"返回值: {result}")
        
        if len(result) == 5:
            print("✓ send_command_async 返回五元组格式正确")
            ok, message, status_code, response_headers, response_body = result
            print(f"  - ok: {ok}")
            print(f"  - message: {message}")
            print(f"  - status_code: {status_code}")
            print(f"  - response_headers: {response_headers}")
            print(f"  - response_body: {response_body[:100]}...")
        else:
            print("✗ send_command_async 返回值格式不正确")
            
        # 测试send_command方法（通过future）
        print("3. 测试send_command方法...")
        future = async_manager.send_command(device, command_dict)
        result = future.result(timeout=10)
        
        print(f"返回值长度: {len(result)}")
        print(f"返回值: {result}")
        
        if len(result) == 5:
            print("✓ send_command 返回五元组格式正确")
            ok, message, status_code, response_headers, response_body = result
            print(f"  - ok: {ok}")
            print(f"  - message: {message}")
            print(f"  - status_code: {status_code}")
            print(f"  - response_headers: {response_headers}")
            print(f"  - response_body: {response_body[:100]}...")
        else:
            print("✗ send_command 返回值格式不正确")
            
        print("\n=== 测试完成 ===")
        
    except Exception as e:
        print(f"测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 清理资源
        async_manager.close()

if __name__ == "__main__":
    asyncio.run(test_async_logging())