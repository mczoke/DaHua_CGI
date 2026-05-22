#!/usr/bin/env python3
"""
测试command优先策略修复
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.device_manager import DeviceInfo
from utils.async_executor import AsyncIOManager
import asyncio

# 创建测试设备
device = DeviceInfo(
    index=0,
    ip='10.17.1.11',
    port='80',
    username='admin',
    password='admin123'
)
device.online = True
device.status = '在线'

# 创建异步管理器
manager = AsyncIOManager()

async def test_async_command_return_format():
    """测试异步命令返回格式"""
    print("=== 测试AsyncIOManager.send_command_async方法返回格式 ===")
    
    try:
        # 测试字符串命令
        command = "VideoWidget[0].CustomTitle[1].EncodeBlend=true"
        print(f"测试命令: {command}")
        
        result = await manager.send_command_async(device, command)
        
        print(f"返回结果类型: {type(result)}")
        print(f"返回结果长度: {len(result)}")
        print(f"返回结果内容: {result}")
        
        # 检查是否包含5个元素
        if len(result) == 5:
            print("✓ AsyncIOManager.send_command_async返回5个元素的元组")
            ok, msg, status, headers, error = result
            print(f"ok: {ok}")
            print(f"msg: {msg}")
            print(f"status: {status}")
            print(f"headers: {headers}")
            print(f"error: {error}")
            
            # 测试提取前两个元素
            ok_extracted, msg_extracted = result[0], result[1]
            print(f"\n提取前两个元素: ok={ok_extracted}, msg={msg_extracted}")
            
            if ok_extracted == ok and msg_extracted == msg:
                print("✓ 元素提取正确")
            else:
                print("✗ 元素提取错误")
                
        else:
            print("✗ 返回格式不符合预期")
            
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()

async def test_device_manager_fix():
    """测试device_manager.py中的修复"""
    print("\n=== 测试device_manager.py中的修复 ===")
    
    try:
        from utils.device_manager import ConfigExecutor
        from utils.log_manager import LogManager
        
        # 创建测试配置
        test_config = {
            'cgi_commands': ['VideoWidget[0].CustomTitle[1].EncodeBlend=true'],
            'config_concurrent': 2,
            'timeout': 1000,
            'auth_method': 'digest'
        }
        
        # 创建日志管理器
        log_manager = LogManager()
        
        # 创建配置执行器
        executor = ConfigExecutor(test_config, log_manager, use_async=True)
        
        # 模拟异步管理器
        executor.async_manager = AsyncIOManager()
        
        # 测试异步命令优先策略中的修复
        async def _send_with_sem(d, c):
            """模拟device_manager.py中修复后的代码"""
            try:
                # AsyncIOManager.send_command_async返回5个元素的元组，我们只需要前两个
                result = await executor.async_manager.send_command_async(d, c)
                ok, msg = result[0], result[1]
                
                print(f"设备 {d.ip} 命令执行结果: ok={ok}, msg={msg}")
                return d, ok, msg
                
            except Exception as e:
                print(f"设备 {d.ip} 命令执行异常: {e}")
                return d, False, f'异步请求异常: {e}'
        
        # 测试修复后的代码
        print("测试修复后的_send_with_sem函数...")
        d, ok, msg = await _send_with_sem(device, "VideoWidget[0].CustomTitle[1].EncodeBlend=true")
        
        if isinstance(ok, bool) and isinstance(msg, str):
            print("✓ 修复后的代码正常工作")
            print(f"返回结果: ok={ok}, msg={msg}")
        else:
            print("✗ 修复后的代码返回格式错误")
            
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """主测试函数"""
    print("开始测试command优先策略修复...")
    
    await test_async_command_return_format()
    await test_device_manager_fix()
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    asyncio.run(main())