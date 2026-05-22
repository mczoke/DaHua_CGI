#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试认证域处理问题
分析Digest认证中的realm处理
"""

import requests
from requests.auth import HTTPDigestAuth
import hashlib
import urllib.parse


def analyze_digest_auth_details(ip, port, username, password):
    """详细分析Digest认证过程"""
    print("🔍 详细分析Digest认证过程")
    print("=" * 80)
    
    url = f"http://{ip}:{port}/cgi-bin/configManager.cgi?action=getConfig&name=General"
    
    # 第一次请求，获取认证信息
    print("1. 获取服务器认证要求:")
    try:
        response = requests.get(url, timeout=5, verify=False)
        print(f"   第一次请求状态: {response.status_code}")
        
        if response.status_code == 401 and 'www-authenticate' in response.headers:
            auth_header = response.headers['www-authenticate']
            print(f"   认证头: {auth_header}")
            
            # 解析认证头
            auth_parts = auth_header.split(', ')
            auth_info = {}
            for part in auth_parts:
                if '=' in part:
                    key, value = part.split('=', 1)
                    auth_info[key.strip()] = value.strip('\"')
            
            print(f"   解析后的认证信息:")
            for key, value in auth_info.items():
                print(f"     {key}: {value}")
            
            # 手动计算Digest认证
            print("\n2. 手动计算Digest认证:")
            realm = auth_info.get('realm', '')
            nonce = auth_info.get('nonce', '')
            qop = auth_info.get('qop', '')
            algorithm = auth_info.get('algorithm', 'MD5')
            
            print(f"   Realm: {realm}")
            print(f"   Nonce: {nonce}")
            print(f"   QoP: {qop}")
            print(f"   Algorithm: {algorithm}")
            
            # 计算HA1
            ha1_input = f"{username}:{realm}:{password}"
            ha1 = hashlib.md5(ha1_input.encode()).hexdigest()
            print(f"   HA1计算: {ha1_input} -> {ha1}")
            
            # 计算HA2
            method = "GET"
            uri = "/cgi-bin/configManager.cgi?action=getConfig&name=General"
            ha2_input = f"{method}:{uri}"
            ha2 = hashlib.md5(ha2_input.encode()).hexdigest()
            print(f"   HA2计算: {method}:{uri} -> {ha2}")
            
            # 计算response
            nc = "00000001"
            cnonce = "0a4f113b"
            response_input = f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}"
            response_hash = hashlib.md5(response_input.encode()).hexdigest()
            print(f"   Response计算: {response_input} -> {response_hash}")
            
            # 构造认证头
            auth_value = f'Digest username="{username}", realm="{realm}", nonce="{nonce}", uri="{uri}", response="{response_hash}", algorithm={algorithm}, qop={qop}, nc={nc}, cnonce="{cnonce}"'
            print(f"   手动构造的认证头: {auth_value}")
            
        else:
            print("   ⚠️ 未获取到认证信息")
            
    except Exception as e:
        print(f"   ❌ 分析失败: {str(e)}")


def test_requests_lib_auth(ip, port, username, password):
    """测试requests库的认证处理"""
    print("\n3. 测试requests库认证处理:")
    print("=" * 80)
    
    url = f"http://{ip}:{port}/cgi-bin/configManager.cgi?action=getConfig&name=General"
    
    # 使用requests的Digest认证
    auth = HTTPDigestAuth(username, password)
    
    # 创建会话，查看认证过程
    session = requests.Session()
    
    # 第一次请求（应该返回401，然后requests会自动重试）
    print("   第一次请求（无认证）:")
    try:
        response = session.get(url, timeout=5, verify=False)
        print(f"     状态码: {response.status_code}")
        
        # 查看请求历史
        if response.history:
            print(f"     重定向历史: {len(response.history)}次")
            for i, hist_resp in enumerate(response.history):
                print(f"     第{i+1}次请求状态: {hist_resp.status_code}")
                if 'www-authenticate' in hist_resp.headers:
                    print(f"       认证头: {hist_resp.headers['www-authenticate']}")
        
    except Exception as e:
        print(f"     ❌ 错误: {str(e)}")
    
    # 第二次请求（使用认证）
    print("\n   第二次请求（使用认证）:")
    try:
        response = session.get(url, auth=auth, timeout=5, verify=False)
        print(f"     状态码: {response.status_code}")
        print(f"     最终URL: {response.url}")
        
        # 查看请求头
        if response.request.headers.get('Authorization'):
            auth_header = response.request.headers['Authorization']
            print(f"     发送的认证头: {auth_header}")
            
            # 解析认证头
            if auth_header.startswith('Digest '):
                auth_parts = auth_header[7:].split(', ')
                print("     解析认证头:")
                for part in auth_parts:
                    print(f"       {part}")
        
        if response.status_code == 200:
            print("     ✅ 认证成功")
        else:
            print("     ❌ 认证失败")
            
    except Exception as e:
        print(f"     ❌ 错误: {str(e)}")


def test_different_auth_methods(ip, port, username, password):
    """测试不同的认证方法"""
    print("\n4. 测试不同认证方法:")
    print("=" * 80)
    
    url = f"http://{ip}:{port}/cgi-bin/configManager.cgi?action=getConfig&name=General"
    
    methods = [
        ("HTTPDigestAuth", HTTPDigestAuth(username, password)),
        ("手动Digest头", None),
    ]
    
    for method_name, auth_obj in methods:
        print(f"   {method_name}:")
        
        try:
            if method_name == "手动Digest头":
                # 先获取认证信息
                response = requests.get(url, timeout=5, verify=False)
                if response.status_code == 401 and 'www-authenticate' in response.headers:
                    auth_header = response.headers['www-authenticate']
                    
                    # 解析认证信息
                    auth_parts = auth_header.split(', ')
                    auth_info = {}
                    for part in auth_parts:
                        if '=' in part:
                            key, value = part.split('=', 1)
                            auth_info[key.strip()] = value.strip('\"')
                    
                    realm = auth_info.get('realm', '')
                    nonce = auth_info.get('nonce', '')
                    
                    # 手动计算
                    uri = "/cgi-bin/configManager.cgi?action=getConfig&name=General"
                    ha1 = hashlib.md5(f"{username}:{realm}:{password}".encode()).hexdigest()
                    ha2 = hashlib.md5(f"GET:{uri}".encode()).hexdigest()
                    response_hash = hashlib.md5(f"{ha1}:{nonce}:00000001:0a4f113b:auth:{ha2}".encode()).hexdigest()
                    
                    auth_header = f'Digest username="{username}", realm="{realm}", nonce="{nonce}", uri="{uri}", response="{response_hash}", algorithm=MD5, qop=auth, nc=00000001, cnonce="0a4f113b"'
                    
                    headers = {'Authorization': auth_header}
                    response = requests.get(url, headers=headers, timeout=5, verify=False)
                
            else:
                response = requests.get(url, auth=auth_obj, timeout=5, verify=False)
            
            print(f"     状态码: {response.status_code}")
            
            if response.status_code == 200:
                print("     ✅ 成功")
            elif response.status_code == 401:
                print("     ❌ 认证失败")
                if 'www-authenticate' in response.headers:
                    print(f"     服务器要求: {response.headers['www-authenticate']}")
            else:
                print(f"     ⚠️ HTTP {response.status_code}")
                
        except Exception as e:
            print(f"     ❌ 错误: {str(e)}")


def main():
    """主函数"""
    print("🔧 认证域调试工具")
    print("=" * 80)
    print("分析Digest认证中的realm处理问题")
    print()
    
    ip = "10.17.1.11"
    port = "80"
    username = "admin"
    password = "Zxkj@8787558"
    
    print(f"测试设备: {ip}:{port}")
    print(f"认证信息: {username}/{password}")
    print()
    
    # 详细分析认证过程
    analyze_digest_auth_details(ip, port, username, password)
    
    # 测试requests库认证
    test_requests_lib_auth(ip, port, username, password)
    
    # 测试不同认证方法
    test_different_auth_methods(ip, port, username, password)
    
    print("\n💡 关键发现:")
    print("1. 服务器使用动态realm和nonce")
    print("2. requests库应该能正确处理Digest认证")
    print("3. 401错误可能是认证请求构造问题")
    print("4. 需要检查实际配置程序中的认证处理")


if __name__ == "__main__":
    main()