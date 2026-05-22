#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试请求构造问题
打印原始请求信息，分析401错误原因
"""

import requests
from requests.auth import HTTPDigestAuth, HTTPBasicAuth
import urllib.parse


def debug_request_construction(ip, port, username, password):
    """调试请求构造过程"""
    print("🔍 调试请求构造过程")
    print("=" * 80)
    
    # 测试命令
    command = "VideoWidget[0].CustomTitle[1].EncodeBlend=true"
    
    # 1. 显示URL构造过程
    print("1. URL构造过程:")
    base_url = f"http://{ip}:{port}/cgi-bin/configManager.cgi"
    print(f"   基础URL: {base_url}")
    
    encoded_cmd = urllib.parse.quote(command, safe='')
    print(f"   原始命令: {command}")
    print(f"   编码后命令: {encoded_cmd}")
    
    full_url = f"{base_url}?action=setConfig&{encoded_cmd}" 
    display_url = f"{base_url}?action=setConfig&{command.replace(' ', '%20')}"
    
    print(f"   完整URL: {full_url}")
    print(f"   显示URL: {display_url}")
    print()
    
    # 2. 显示认证头构造
    print("2. 认证头构造:")
    
    # Digest认证
    auth_digest = HTTPDigestAuth(username, password)
    print(f"   Digest认证对象: {auth_digest}")
    
    # Basic认证
    auth_basic = HTTPBasicAuth(username, password)
    print(f"   Basic认证对象: {auth_basic}")
    
    # 手动构造Basic认证头
    import base64
    credentials = f"{username}:{password}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    basic_auth_header = f"Basic {encoded_credentials}"
    print(f"   手动Basic认证头: {basic_auth_header}")
    print()
    
    # 3. 测试不同认证方式
    print("3. 测试不同认证方式:")
    
    test_cases = [
        ("Digest认证", "digest"),
        ("Basic认证", "basic"),
        ("手动Basic头", "manual_basic"),
        ("无认证", "none")
    ]
    
    for test_name, auth_type in test_cases:
        print(f"   {test_name}:")
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Accept': '*/*',
                'Connection': 'close'
            }
            
            if auth_type == "digest":
                auth = HTTPDigestAuth(username, password)
                response = requests.get(full_url, auth=auth, headers=headers, timeout=10, verify=False)
            elif auth_type == "basic":
                auth = HTTPBasicAuth(username, password)
                response = requests.get(full_url, auth=auth, headers=headers, timeout=10, verify=False)
            elif auth_type == "manual_basic":
                headers['Authorization'] = basic_auth_header
                response = requests.get(full_url, headers=headers, timeout=10, verify=False)
            else:
                response = requests.get(full_url, headers=headers, timeout=10, verify=False)
            
            # 打印请求详情
            print(f"     请求URL: {response.request.url}")
            print(f"     请求方法: {response.request.method}")
            print(f"     请求头: {dict(response.request.headers)}")
            print(f"     响应状态: {response.status_code}")
            
            if response.status_code == 200:
                print(f"     ✅ 成功")
            elif response.status_code == 401:
                print(f"     ❌ 认证失败")
                # 打印服务器返回的认证头
                if 'www-authenticate' in response.headers:
                    print(f"     服务器认证要求: {response.headers['www-authenticate']}")
            else:
                print(f"     ⚠️ HTTP {response.status_code}")
                
        except Exception as e:
            print(f"     ❌ 错误: {str(e)}")
        
        print()


def test_different_endpoints(ip, port, username, password):
    """测试不同的CGI端点"""
    print("4. 测试不同CGI端点:")
    print("=" * 80)
    
    endpoints = [
        ("获取配置", "getConfig&name=General"),
        ("设置配置", "setConfig&VideoWidget[0].CustomTitle[1].EncodeBlend=true"),
        ("获取设备信息", "getDeviceInfo"),
        ("获取版本", "getVersion"),
        ("获取时间", "getTime"),
    ]
    
    for endpoint_name, endpoint in endpoints:
        print(f"   {endpoint_name}:")
        
        url = f"http://{ip}:{port}/cgi-bin/configManager.cgi?action={endpoint}"
        
        try:
            auth = HTTPDigestAuth(username, password)
            response = requests.get(url, auth=auth, timeout=5, verify=False)
            
            print(f"     请求URL: {response.request.url}")
            print(f"     响应状态: {response.status_code}")
            
            if response.status_code == 200:
                print(f"     ✅ 成功")
                # 显示部分响应内容
                content_preview = response.text[:200] if response.text else "空响应"
                print(f"     响应预览: {content_preview}")
            elif response.status_code == 401:
                print(f"     ❌ 认证失败")
            else:
                print(f"     ⚠️ HTTP {response.status_code}")
                
        except Exception as e:
            print(f"     ❌ 错误: {str(e)}")
        
        print()


def analyze_authentication_requirements(ip, port):
    """分析认证要求"""
    print("5. 分析认证要求:")
    print("=" * 80)
    
    url = f"http://{ip}:{port}/cgi-bin/configManager.cgi?action=getConfig&name=General"
    
    try:
        # 发送无认证请求，获取服务器认证要求
        response = requests.get(url, timeout=5, verify=False)
        
        print(f"   无认证请求状态: {response.status_code}")
        
        if response.status_code == 401:
            if 'www-authenticate' in response.headers:
                auth_header = response.headers['www-authenticate']
                print(f"   服务器认证要求: {auth_header}")
                
                # 分析认证类型
                if 'digest' in auth_header.lower():
                    print("   ✅ 服务器要求Digest认证")
                elif 'basic' in auth_header.lower():
                    print("   ✅ 服务器要求Basic认证")
                else:
                    print("   ⚠️ 未知认证类型")
                    
                # 分析realm
                if 'realm=' in auth_header:
                    realm_start = auth_header.find('realm=') + 6
                    realm_end = auth_header.find('"', realm_start)
                    realm = auth_header[realm_start:realm_end]
                    print(f"   认证域(Realm): {realm}")
            else:
                print("   ⚠️ 服务器未提供认证要求信息")
        else:
            print("   ⚠️ 服务器未要求认证")
            
    except Exception as e:
        print(f"   ❌ 分析失败: {str(e)}")


def main():
    """主函数"""
    print("🔧 请求构造调试工具")
    print("=" * 80)
    print("分析401错误原因，检查请求构造问题")
    print()
    
    # 使用实际设备信息
    ip = "10.17.1.11"
    port = "80"
    username = "admin"
    password = "Zxkj@8787558"  # 您提供的正确密码
    
    print(f"测试设备: {ip}:{port}")
    print(f"认证信息: {username}/{password}")
    print()
    
    # 调试请求构造
    debug_request_construction(ip, port, username, password)
    
    # 测试不同端点
    test_different_endpoints(ip, port, username, password)
    
    # 分析认证要求
    analyze_authentication_requirements(ip, port)
    
    print("\n💡 分析建议:")
    print("1. 检查服务器返回的认证要求头(WWW-Authenticate)")
    print("2. 确认认证域(Realm)是否正确")
    print("3. 检查URL编码是否正确")
    print("4. 验证CGI端点是否可用")
    print("5. 检查设备固件版本和CGI支持情况")


if __name__ == "__main__":
    main()