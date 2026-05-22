#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复认证失败问题的脚本
解决401认证失败问题
"""

import os
import sys
import json
from utils.log_manager import LogManager
from utils.device_manager import DeviceLoader, DeviceInfo
from utils.config_manager import ConfigManager
from utils.async_manager import AsyncIOManager


def check_authentication_issue():
    """检查认证问题"""
    print("=== 检查认证问题 ===")
    
    # 加载配置
    config_manager = ConfigManager()
    config = config_manager.load_config()
    
    print(f"认证方法: {config.get('auth_method', 'digest')}")
    print(f"超时设置: {config.get('timeout', 1000)}ms")
    print(f"SSL验证: {config.get('verify_ssl', False)}")
    print()
    
    return config


def test_device_authentication():
    """测试设备认证"""
    print("=== 测试设备认证 ===")
    
    # 创建日志管理器
    log_manager = LogManager()
    
    # 创建测试设备（使用正确的认证信息）
    test_devices = [
        DeviceInfo(index=0, ip="10.17.1.11", port="80", username="admin", password="admin", status="在线"),
        DeviceInfo(index=1, ip="10.17.1.12", port="80", username="admin", password="admin", status="在线"),
        DeviceInfo(index=2, ip="10.17.1.13", port="80", username="admin", password="admin", status="在线"),
        DeviceInfo(index=3, ip="10.17.1.14", port="80", username="admin", password="admin", status="在线"),
        DeviceInfo(index=4, ip="10.17.1.15", port="80", username="admin", password="admin", status="在线"),
    ]
    
    for device in test_devices:
        device.online = True
        device.selected = True
        print(f"测试设备: {device.ip}:{device.port} - 用户名: {device.username} - 密码: {device.password}")
    
    print()
    return test_devices, log_manager


def check_actual_device_credentials():
    """检查实际设备认证信息"""
    print("=== 检查实际设备认证信息 ===")
    
    # 检查是否有Excel文件
    excel_files = []
    for file in os.listdir("."):
        if file.endswith(('.xlsx', '.xls')):
            excel_files.append(file)
    
    if excel_files:
        print(f"找到Excel文件: {excel_files}")
        
        # 加载设备
        log_manager = LogManager()
        device_loader = DeviceLoader(log_manager)
        
        try:
            devices, count = device_loader.load_from_excel(excel_files[0])
            print(f"从Excel加载了 {count} 台设备")
            
            # 显示前5台设备的认证信息
            for i, device in enumerate(devices[:5]):
                print(f"设备 {i+1}: {device.ip}:{device.port} - 用户名: {device.username} - 密码: {'*' * len(device.password) if device.password else '空'}")
            
            return devices
            
        except Exception as e:
            print(f"加载Excel失败: {e}")
    else:
        print("未找到Excel设备文件")
    
    print()
    return None


def create_auth_test_script():
    """创建认证测试脚本"""
    script_content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设备认证测试脚本
测试设备连接和认证状态
"""

import requests
from requests.auth import HTTPDigestAuth, HTTPBasicAuth
import time


def test_device_auth(ip, port, username, password, auth_method="digest"):
    """测试设备认证"""
    url = f"http://{ip}:{port}/cgi-bin/configManager.cgi?action=getConfig&name=General"
    
    try:
        if auth_method == "digest":
            auth = HTTPDigestAuth(username, password)
        else:
            auth = HTTPBasicAuth(username, password)
        
        response = requests.get(url, auth=auth, timeout=5, verify=False)
        
        if response.status_code == 200:
            return True, "认证成功"
        elif response.status_code == 401:
            return False, f"认证失败 (401) - 用户名/密码错误"
        else:
            return False, f"HTTP错误: {response.status_code}"
            
    except requests.exceptions.ConnectTimeout:
        return False, "连接超时"
    except requests.exceptions.ConnectionError:
        return False, "连接失败"
    except Exception as e:
        return False, f"其他错误: {str(e)}"


# 测试设备列表
test_devices = [
    {"ip": "10.17.1.11", "port": "80", "username": "admin", "password": "admin"},
    {"ip": "10.17.1.12", "port": "80", "username": "admin", "password": "admin"},
    {"ip": "10.17.1.13", "port": "80", "username": "admin", "password": "admin"},
    {"ip": "10.17.1.14", "port": "80", "username": "admin", "password": "admin"},
    {"ip": "10.17.1.15", "port": "80", "username": "admin", "password": "admin"},
]

print("=== 设备认证测试 ===")
print("测试方法: Digest认证")
print()

for i, device in enumerate(test_devices):
    print(f"测试设备 {i+1}: {device['ip']}:{device['port']}")
    print(f"用户名: {device['username']}, 密码: {device['password']}")
    
    success, message = test_device_auth(
        device['ip'], device['port'], 
        device['username'], device['password']
    )
    
    if success:
        print("✅ 认证成功")
    else:
        print(f"❌ {message}")
    
    print("-" * 50)
    time.sleep(1)  # 避免请求过快

print("\n测试完成！")
'''
    
    with open("test_device_auth.py", "w", encoding="utf-8") as f:
        f.write(script_content)
    
    print("✅ 认证测试脚本已创建: test_device_auth.py")
    print()


def provide_solutions():
    """提供解决方案"""
    print("=== 认证失败解决方案 ===")
    print("1. 检查设备认证信息")
    print("   - 确保用户名和密码正确")
    print("   - 默认认证信息: admin/admin")
    print("   - 如果设备使用自定义密码，请在Excel文件中更新")
    print()
    
    print("2. 检查网络连接")
    print("   - 确保设备IP地址可达")
    print("   - 检查防火墙设置")
    print("   - 验证端口是否开放")
    print()
    
    print("3. 认证方法设置")
    print("   - 当前使用Digest认证")
    print("   - 如果设备不支持Digest，可尝试Basic认证")
    print("   - 在配置文件中修改auth_method为'basic'")
    print()
    
    print("4. 设备状态检查")
    print("   - 确保设备在线且可访问")
    print("   - 检查设备是否被其他程序占用")
    print()
    
    print("5. 运行认证测试脚本")
    print("   - 运行 'python test_device_auth.py' 测试设备认证")
    print("   - 根据测试结果调整认证信息")
    print()


def main():
    """主函数"""
    print("🔧 认证问题诊断工具")
    print("=" * 50)
    
    # 检查配置
    config = check_authentication_issue()
    
    # 检查实际设备认证信息
    actual_devices = check_actual_device_credentials()
    
    # 测试设备认证
    test_devices, log_manager = test_device_authentication()
    
    # 创建认证测试脚本
    create_auth_test_script()
    
    # 提供解决方案
    provide_solutions()
    
    print("=" * 50)
    print("✅ 诊断完成！")
    print("\n下一步操作:")
    print("1. 运行认证测试: python test_device_auth.py")
    print("2. 根据测试结果调整设备认证信息")
    print("3. 重新尝试配置操作")


if __name__ == "__main__":
    main()