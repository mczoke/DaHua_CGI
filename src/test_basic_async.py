#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基本异步功能测试脚本
测试AsyncIOManager的基本功能
"""

import sys
import os
import asyncio

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.async_executor import AsyncIOManager

class MockDevice:
    """模拟设备类"""
    def __init__(self, ip, port=80, username="admin", password="admin"):
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password

async def test_basic_async():
    """测试基本异步功能"""
    print("=== 基本异步功能测试 ===")
    
    # 创建AsyncIOManager
    async_manager = AsyncIOManager(timeout=5, auth_method='digest')
    
    # 创建测试设备
    device = MockDevice("192.168.1.100", 80, "admin", "admin")
    
    try:
        # 测试基本命令发送
        print("测试基本命令发送...")
        result = await async_manager.send_command_async(device, "VideoWidget[0].CustomTitle[1]=测试标题")
        print(f"基本命令测试结果: {result}")
        
        # 测试URL认证命令发送
        print("测试URL认证命令发送...")
        result = await async_manager.send_command_async(device, "VideoWidget[0].CustomTitle[1]=测试标题", use_url_auth=True)
        print(f"URL认证测试结果: {result}")
        
        return True
        
    except Exception as e:
        print(f"测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        async_manager.close()

async def main():
    """主测试函数"""
    print("开始基本异步功能测试...")
    
    result = await test_basic_async()
    
    print("\n=== 测试结果 ===")
    if result:
        print("✅ 基本异步功能测试通过！")
    else:
        print("❌ 基本异步功能测试失败")
    
    return result

if __name__ == "__main__":
    # 运行测试
    result = asyncio.run(main())
    sys.exit(0 if result else 1)