#!/usr/bin/env python3
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
    {"ip": "10.17.1.16", "port": "80", "username": "admin", "password": "admin"},
    {"ip": "10.17.1.17", "port": "80", "username": "admin", "password": "admin"},
    {"ip": "10.17.1.18", "port": "80", "username": "admin", "password": "admin"},
    {"ip": "10.17.1.19", "port": "80", "username": "admin", "password": "admin"},
    {"ip": "10.17.1.20", "port": "80", "username": "admin", "password": "admin"},
]

print("=== 设备认证测试 ===")
print("测试方法: Digest认证")
print()

success_count = 0
failure_count = 0

for i, device in enumerate(test_devices):
    print(f"测试设备 {i+1}: {device['ip']}:{device['port']}")
    print(f"用户名: {device['username']}, 密码: {device['password']}")
    
    success, message = test_device_auth(
        device['ip'], device['port'], 
        device['username'], device['password']
    )
    
    if success:
        print("✅ 认证成功")
        success_count += 1
    else:
        print(f"❌ {message}")
        failure_count += 1
    
    print("-" * 50)
    time.sleep(1)  # 避免请求过快

print(f"\n测试结果统计:")
print(f"✅ 成功: {success_count} 台设备")
print(f"❌ 失败: {failure_count} 台设备")

if failure_count > 0:
    print("\n⚠️ 认证失败原因分析:")
    print("1. 设备不在线或网络不可达")
    print("2. 用户名/密码不正确")
    print("3. 设备不支持Digest认证")
    print("4. 防火墙或网络限制")
    print("\n💡 解决方案:")
    print("1. 检查设备实际IP地址和端口")
    print("2. 验证用户名和密码是否正确")
    print("3. 尝试Basic认证方法")
    print("4. 检查网络连接和防火墙设置")

print("\n测试完成！")