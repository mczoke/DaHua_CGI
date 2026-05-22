#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试修复后的异步配置功能
验证401错误是否已解决
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.device_manager import DeviceLoader, ConfigExecutor
from utils.log_manager import LogManager
from utils.async_executor import AsyncIOManager
import time


def test_fixed_async_config():
    """测试修复后的异步配置功能"""
    print("🔧 测试修复后的异步配置功能")
    print("=" * 80)
    
    # 创建设备列表
    devices = []
    for i in range(11, 21):  # 10.17.1.11-20
        from utils.device_manager import Device
        device = Device(f"10.17.1.{i}", "80")
        device.username = "admin"
        device.password = "Zxkj@8787558"
        device.online = True
        device.status = "在线"
        device.selected = True
        devices.append(device)
    
    print(f"测试设备数量: {len(devices)}")
    for device in devices:
        print(f"  {device.ip}:{device.port} - {device.username}/{device.password}")
    print()
    
    # 创建配置
    config = {
        "auth_method": "digest",
        "timeout": 5000,
        "config_concurrent": 5,
        "auto_save_results": True,
        "auto_skip_offline": True
    }
    
    # 创建日志管理器
    log_manager = LogManager()
    
    # 创建异步管理器
    async_manager = AsyncIOManager(
        timeout=10,
        verify_ssl=False,
        max_connections=10,
        auth_method="digest"
    )
    
    # 创建配置执行器（启用异步模式）
    executor = ConfigExecutor(config, log_manager, use_async=True)
    executor.async_manager = async_manager
    
    # 测试命令
    test_commands = [
        "VideoWidget[0].CustomTitle[1].EncodeBlend=true",
        "VideoWidget[0].CustomTitle[1].Text=测试标题"
    ]
    
    print("测试命令:")
    for cmd in test_commands:
        print(f"  {cmd}")
    print()
    
    # 执行测试
    print("开始异步配置测试...")
    
    def progress_callback(completed, total, current_device=None):
        if current_device:
            print(f"进度: {completed}/{total} - 当前设备: {current_device.ip}")
        else:
            print(f"进度: {completed}/{total}")
    
    try:
        # 执行批量配置
        results = executor.execute_batch(
            devices=devices,
            mode="standard",
            exec_strategy="device_first",
            progress_callback=progress_callback
        )
        
        print("\n测试完成!")
        print("=" * 80)
        
        # 分析结果
        success_count = 0
        failure_count = 0
        
        for result in results:
            if result.get('success', False):
                success_count += 1
                print(f"✅ {result['ip']}: 成功 ({result['success_commands']}/{result['total_commands']}命令)")
            else:
                failure_count += 1
                print(f"❌ {result['ip']}: 失败 - {result.get('failure_details', '未知错误')}")
        
        print(f"\n统计结果:")
        print(f"  成功: {success_count}台设备")
        print(f"  失败: {failure_count}台设备")
        print(f"  成功率: {success_count/len(devices)*100:.1f}%")
        
        # 检查是否有401错误
        auth_failures = [r for r in results if '401' in str(r.get('failure_details', ''))]
        if auth_failures:
            print(f"\n⚠️ 发现认证失败: {len(auth_failures)}台设备")
            for failure in auth_failures:
                print(f"  {failure['ip']}: {failure.get('failure_details', '')}")
        else:
            print("\n✅ 未发现401认证错误")
            
    except Exception as e:
        print(f"❌ 测试异常: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 清理资源
        if async_manager:
            try:
                async_manager._loop.call_soon_threadsafe(async_manager._loop.stop)
            except:
                pass


def test_single_device_async():
    """测试单个设备的异步配置"""
    print("\n🧪 测试单个设备的异步配置")
    print("=" * 80)
    
    from utils.device_manager import Device
    
    # 创建单个设备
    device = Device("10.17.1.11", "80")
    device.username = "admin"
    device.password = "Zxkj@8787558"
    device.online = True
    device.status = "在线"
    device.selected = True
    
    print(f"测试设备: {device.ip}:{device.port}")
    print(f"认证信息: {device.username}/{device.password}")
    
    # 创建配置
    config = {
        "auth_method": "digest",
        "timeout": 5000,
        "config_concurrent": 1,
        "auto_save_results": True
    }
    
    # 创建日志管理器
    log_manager = LogManager()
    
    # 创建异步管理器
    async_manager = AsyncIOManager(
        timeout=10,
        verify_ssl=False,
        max_connections=1,
        auth_method="digest"
    )
    
    # 创建配置执行器（启用异步模式）
    executor = ConfigExecutor(config, log_manager, use_async=True)
    executor.async_manager = async_manager
    
    # 测试命令
    test_command = "VideoWidget[0].CustomTitle[1].EncodeBlend=true"
    
    print(f"测试命令: {test_command}")
    print("开始测试...")
    
    try:
        # 使用异步方式发送单个命令
        future = async_manager.send_command(device, test_command)
        result = future.result(timeout=10)
        
        print(f"异步结果: {result}")
        
        if result[0]:  # ok字段
            print("✅ 异步配置成功")
        else:
            print(f"❌ 异步配置失败: {result[1]}")
            
    except Exception as e:
        print(f"❌ 异步测试异常: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 清理资源
        if async_manager:
            try:
                async_manager._loop.call_soon_threadsafe(async_manager._loop.stop)
            except:
                pass


def check_async_executor_fix():
    """检查异步执行器修复情况"""
    print("🔍 检查异步执行器修复情况")
    print("=" * 80)
    
    file_path = "c:\\Users\\Administrator\\Desktop\\CGI\\V9.6\\V9.5_Enhanced_Logging\\utils\\async_executor.py"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查修复后的函数
        if '"""修复版：正确解析WWW-Authenticate头，支持带引号的值"""' in content:
            print("✅ _parse_www_authenticate函数已修复")
        else:
            print("❌ _parse_www_authenticate函数未修复")
        
        # 检查改进的正则表达式
        if r'pattern = r\'(\\w+)=\\"([^\\"]+)\\"|(\\w+)=([^,\\s]+)\'' in content:
            print("✅ 正则表达式已改进")
        else:
            print("❌ 正则表达式未改进")
            
    except Exception as e:
        print(f"❌ 检查失败: {str(e)}")


def main():
    """主函数"""
    print("🔧 修复后异步配置功能测试")
    print("=" * 80)
    print("验证401认证错误是否已解决")
    print()
    
    # 1. 检查修复情况
    check_async_executor_fix()
    
    # 2. 测试单个设备异步配置
    test_single_device_async()
    
    # 3. 测试批量异步配置
    test_fixed_async_config()
    
    print("\n💡 测试完成!")
    print("如果仍有401错误，请检查:")
    print("1. 设备网络连接状态")
    print("2. 设备认证信息是否正确")
    print("3. 设备CGI接口是否可用")
    print("4. 防火墙或网络限制")


if __name__ == "__main__":
    main()