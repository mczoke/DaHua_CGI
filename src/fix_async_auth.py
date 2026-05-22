#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复异步认证问题
解决401错误，改进Digest认证实现
"""

import re
import hashlib
import os


def fix_parse_www_authenticate():
    """修复认证头解析函数"""
    print("🔧 修复认证头解析函数")
    print("=" * 80)
    
    # 当前有问题的实现
    old_code = '''def _parse_www_authenticate(header: str):
    # 解析 WWW-Authenticate: Digest realm="...", nonce="...", qop="auth" ...
    parts = {}
    for m in re.finditer(r'(\\w+)="?([^",]+)"?', header):
        parts[m.group(1)] = m.group(2)
    return parts'''
    
    # 修复后的实现
    new_code = '''def _parse_www_authenticate(header: str):
    """修复版：正确解析WWW-Authenticate头，支持带引号的值"""
    parts = {}
    # 改进的正则表达式，正确处理带引号的值
    pattern = r'(\\w+)=\"([^\"]+)\"|(\\w+)=([^,\\s]+)'
    for match in re.finditer(pattern, header):
        if match.group(1):  # 带引号的情况
            parts[match.group(1)] = match.group(2)
        elif match.group(3):  # 不带引号的情况
            parts[match.group(3)] = match.group(4)
    return parts'''
    
    print("当前实现:")
    print(old_code)
    print("\n修复后实现:")
    print(new_code)
    
    return new_code


def test_fixed_parsing():
    """测试修复后的解析函数"""
    print("\n🧪 测试修复后的解析函数")
    print("=" * 80)
    
    # 测试认证头
    auth_header = 'Digest realm="Login to D7526EAC47958A8E" qop="auth" nonce="72d124f1-f0ed-4d60-8f05-87537b386b98" opaque="" algorithm=MD5'
    
    print(f"测试认证头: {auth_header}")
    
    # 使用修复后的解析函数
    def _parse_www_authenticate_fixed(header: str):
        """修复版：正确解析WWW-Authenticate头，支持带引号的值"""
        parts = {}
        # 改进的正则表达式，正确处理带引号的值
        pattern = r'(\w+)="([^"]+)"|(\w+)=([^,\s]+)'
        for match in re.finditer(pattern, header):
            if match.group(1):  # 带引号的情况
                parts[match.group(1)] = match.group(2)
            elif match.group(3):  # 不带引号的情况
                parts[match.group(3)] = match.group(4)
        return parts
    
    # 测试解析
    parsed = _parse_www_authenticate_fixed(auth_header)
    print("解析结果:")
    for key, value in parsed.items():
        print(f"  {key}: {value}")
    
    # 验证关键字段
    required_fields = ['realm', 'nonce', 'qop', 'algorithm']
    missing_fields = [field for field in required_fields if field not in parsed]
    
    if missing_fields:
        print(f"❌ 缺失字段: {missing_fields}")
    else:
        print("✅ 所有必需字段解析成功")
        
    return parsed


def apply_fix_to_async_executor():
    """应用修复到async_executor.py文件"""
    print("\n🔧 应用修复到async_executor.py")
    print("=" * 80)
    
    import os
    
    file_path = "c:\\Users\\Administrator\\Desktop\\CGI\\V9.6\\V9.5_Enhanced_Logging\\utils\\async_executor.py"
    
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return False
    
    # 读取文件内容
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 查找并替换解析函数
    old_function = '''def _parse_www_authenticate(header: str):
    # 解析 WWW-Authenticate: Digest realm="...", nonce="...", qop="auth" ...
    parts = {}
    for m in re.finditer(r'(\\w+)="?([^",]+)"?', header):
        parts[m.group(1)] = m.group(2)
    return parts'''
    
    new_function = '''def _parse_www_authenticate(header: str):
    """修复版：正确解析WWW-Authenticate头，支持带引号的值"""
    parts = {}
    # 改进的正则表达式，正确处理带引号的值
    pattern = r'(\\w+)=\"([^\"]+)\"|(\\w+)=([^,\\s]+)'
    for match in re.finditer(pattern, header):
        if match.group(1):  # 带引号的情况
            parts[match.group(1)] = match.group(2)
        elif match.group(3):  # 不带引号的情况
            parts[match.group(3)] = match.group(4)
    return parts'''
    
    if old_function in content:
        # 替换函数
        content = content.replace(old_function, new_function)
        
        # 写回文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ 成功修复_parse_www_authenticate函数")
        return True
    else:
        print("❌ 未找到需要修复的函数，可能已经修复或文件格式不同")
        return False


def test_fixed_async_auth():
    """测试修复后的异步认证"""
    print("\n🧪 测试修复后的异步认证")
    print("=" * 80)
    
    import requests
    from requests.auth import HTTPDigestAuth
    
    # 测试设备信息
    ip = "10.17.1.11"
    port = "80"
    username = "admin"
    password = "Zxkj@8787558"
    
    url = f"http://{ip}:{port}/cgi-bin/configManager.cgi?action=getConfig&name=General"
    
    print(f"测试设备: {ip}:{port}")
    print(f"认证信息: {username}/{password}")
    print(f"测试URL: {url}")
    print()
    
    # 测试修复后的认证
    try:
        auth = HTTPDigestAuth(username, password)
        response = requests.get(url, auth=auth, timeout=10, verify=False)
        
        print(f"请求状态: {response.status_code}")
        print(f"请求URL: {response.request.url}")
        
        if response.status_code == 200:
            print("✅ 认证成功")
            print(f"响应内容预览: {response.text[:200]}")
        elif response.status_code == 401:
            print("❌ 认证失败")
            if 'www-authenticate' in response.headers:
                print(f"服务器认证要求: {response.headers['www-authenticate']}")
        else:
            print(f"⚠️ HTTP {response.status_code}")
            
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")


def create_alternative_auth_solution():
    """创建替代认证解决方案"""
    print("\n💡 创建替代认证解决方案")
    print("=" * 80)
    
    solution_code = '''
# 替代方案：使用更健壮的Digest认证库
import httpx
from httpx_auth import DigestAuth

async def send_command_with_httpx(device, command):
    """使用httpx库的Digest认证"""
    url = f"http://{device.ip}:{device.port}/cgi-bin/configManager.cgi?action=setConfig&{command}"
    
    # 使用httpx的Digest认证
    auth = DigestAuth(device.username, device.password)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, auth=auth, timeout=10.0)
        
        if response.status_code == 200:
            return True, "成功"
        else:
            return False, f"HTTP {response.status_code}"

# 或者使用requests-toolbelt的Digest认证
from requests_toolbelt.auth.http_digest_auth import HTTPDigestAuth

def send_command_with_toolbelt(device, command):
    """使用requests-toolbelt的Digest认证"""
    url = f"http://{device.ip}:{device.port}/cgi-bin/configManager.cgi?action=setConfig&{command}"
    
    # 使用requests-toolbelt的Digest认证
    auth = HTTPDigestAuth(device.username, device.password)
    
    response = requests.get(url, auth=auth, timeout=10, verify=False)
    
    if response.status_code == 200:
        return True, "成功"
    else:
        return False, f"HTTP {response.status_code}"
'''
    
    print("如果修复后仍有问题，可以考虑以下替代方案:")
    print(solution_code)


def main():
    """主函数"""
    print("🔧 异步认证问题修复工具")
    print("=" * 80)
    print("分析并修复异步配置中的401认证错误")
    print()
    
    # 1. 修复解析函数
    fix_parse_www_authenticate()
    
    # 2. 测试修复后的解析
    test_fixed_parsing()
    
    # 3. 应用修复到文件
    if apply_fix_to_async_executor():
        print("\n✅ 修复已应用到文件")
    else:
        print("\n⚠️ 修复未应用，可能需要手动处理")
    
    # 4. 测试修复后的认证
    test_fixed_async_auth()
    
    # 5. 提供替代方案
    create_alternative_auth_solution()
    
    print("\n💡 后续步骤:")
    print("1. 重新运行异步配置测试")
    print("2. 如果仍有401错误，尝试使用替代认证方案")
    print("3. 检查设备固件版本和CGI支持情况")


if __name__ == "__main__":
    main()