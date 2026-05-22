#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
详细诊断脚本 - 检查设备连接、认证和配置问题
"""

import requests
import socket
import time
from requests.auth import HTTPDigestAuth, HTTPBasicAuth


def check_network_connectivity(ip, port=80):
    """检查网络连通性"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((ip, int(port)))
        sock.close()
        
        if result == 0:
            return True, "端口开放"
        else:
            return False, f"端口关闭 (错误码: {result})"
    except Exception as e:
        return False, f"连接异常: {str(e)}"


def test_http_access(ip, port=80):
    """测试HTTP访问"""
    url = f"http://{ip}:{port}/"
    
    try:
        response = requests.get(url, timeout=5, verify=False)
        
        if response.status_code == 200:
            return True, "HTTP访问正常"
        elif response.status_code == 401:
            return True, "HTTP访问正常 (需要认证)"
        else:
            return False, f"HTTP错误: {response.status_code}"
    except Exception as e:
        return False, f"HTTP访问失败: {str(e)}"


def test_cgi_endpoint(ip, port=80):
    """测试CGI端点"""
    url = f"http://{ip}:{port}/cgi-bin/configManager.cgi"
    
    try:
        response = requests.get(url, timeout=5, verify=False)
        
        if response.status_code in [200, 401]:
            return True, "CGI端点可访问"
        else:
            return False, f"CGI端点错误: {response.status_code}"
    except Exception as e:
        return False, f"CGI端点访问失败: {str(e)}"


def test_authentication(ip, port, username, password, auth_method="digest"):
    """测试认证"""
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
            return False, "认证失败 (401) - 用户名/密码错误"
        else:
            return False, f"HTTP错误: {response.status_code}"
    except Exception as e:
        return False, f"认证异常: {str(e)}"


def test_config_command(ip, port, username, password, auth_method="digest"):
    """测试配置命令"""
    # 使用一个简单的配置命令进行测试
    command = "VideoWidget[0].CustomTitle[1].EncodeBlend=true"
    encoded_cmd = requests.utils.quote(command, safe='')
    url = f"http://{ip}:{port}/cgi-bin/configManager.cgi?action=setConfig&{encoded_cmd}"
    
    try:
        if auth_method == "digest":
            auth = HTTPDigestAuth(username, password)
        else:
            auth = HTTPBasicAuth(username, password)
        
        response = requests.get(url, auth=auth, timeout=5, verify=False)
        
        if response.status_code == 200:
            return True, "配置命令执行成功"
        elif response.status_code == 401:
            return False, "配置命令认证失败 (401)"
        else:
            return False, f"配置命令错误: {response.status_code}"
    except Exception as e:
        return False, f"配置命令异常: {str(e)}"


def diagnose_device(ip, port="80", username="admin", password="admin"):
    """诊断单个设备"""
    print(f"\n🔍 诊断设备: {ip}:{port}")
    print("=" * 60)
    
    # 1. 检查网络连通性
    print("1. 网络连通性检查...")
    network_ok, network_msg = check_network_connectivity(ip, port)
    print(f"   {'✅' if network_ok else '❌'} {network_msg}")
    
    if not network_ok:
        print("   ⚠️ 网络不可达，跳过后续测试")
        return False
    
    # 2. 检查HTTP访问
    print("2. HTTP访问检查...")
    http_ok, http_msg = test_http_access(ip, port)
    print(f"   {'✅' if http_ok else '❌'} {http_msg}")
    
    # 3. 检查CGI端点
    print("3. CGI端点检查...")
    cgi_ok, cgi_msg = test_cgi_endpoint(ip, port)
    print(f"   {'✅' if cgi_ok else '❌'} {cgi_msg}")
    
    # 4. 测试认证 (Digest)
    print("4. Digest认证测试...")
    auth_digest_ok, auth_digest_msg = test_authentication(ip, port, username, password, "digest")
    print(f"   {'✅' if auth_digest_ok else '❌'} {auth_digest_msg}")
    
    # 5. 测试认证 (Basic)
    print("5. Basic认证测试...")
    auth_basic_ok, auth_basic_msg = test_authentication(ip, port, username, password, "basic")
    print(f"   {'✅' if auth_basic_ok else '❌'} {auth_basic_msg}")
    
    # 6. 测试配置命令
    print("6. 配置命令测试...")
    config_ok, config_msg = test_config_command(ip, port, username, password, "digest")
    print(f"   {'✅' if config_ok else '❌'} {config_msg}")
    
    # 总结
    print("\n📊 诊断总结:")
    tests = [
        ("网络连通性", network_ok),
        ("HTTP访问", http_ok),
        ("CGI端点", cgi_ok),
        ("Digest认证", auth_digest_ok),
        ("Basic认证", auth_basic_ok),
        ("配置命令", config_ok)
    ]
    
    passed = sum(1 for _, ok in tests if ok)
    total = len(tests)
    
    print(f"   通过测试: {passed}/{total}")
    
    if passed == total:
        print("   ✅ 设备状态正常，可以配置")
        return True
    else:
        print("   ❌ 设备存在问题，需要修复")
        
        # 提供修复建议
        if not auth_digest_ok and not auth_basic_ok:
            print("   💡 认证失败建议:")
            print("      - 检查用户名和密码是否正确")
            print("      - 确认设备支持哪种认证方式")
        
        if not cgi_ok:
            print("   💡 CGI端点问题建议:")
            print("      - 确认设备支持CGI配置")
            print("      - 检查设备固件版本")
        
        return False


def main():
    """主函数"""
    print("🔧 设备配置问题详细诊断工具")
    print("=" * 60)
    
    # 获取用户输入的设备信息
    print("请输入设备信息 (按回车使用默认值):")
    
    ip = input("设备IP地址 [10.17.1.11]: ").strip()
    if not ip:
        ip = "10.17.1.11"
    
    port = input("端口 [80]: ").strip()
    if not port:
        port = "80"
    
    username = input("用户名 [admin]: ").strip()
    if not username:
        username = "admin"
    
    password = input("密码 [admin]: ").strip()
    if not password:
        password = "admin"
    
    print(f"\n开始诊断设备: {ip}:{port}")
    print(f"认证信息: {username}/{password}")
    
    # 执行诊断
    success = diagnose_device(ip, port, username, password)
    
    if success:
        print("\n🎉 诊断完成！设备可以正常配置。")
    else:
        print("\n⚠️ 诊断完成！请根据建议修复问题后重试。")
    
    # 提供批量测试选项
    print("\n💡 批量测试选项:")
    print("   运行 'python test_device_auth.py' 测试所有设备")
    print("   运行 'python fix_auth_issue.py' 进行自动修复")


if __name__ == "__main__":
    main()