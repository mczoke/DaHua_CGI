#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试异步执行器内部请求构造
分析quote_from_bytes错误和认证失败原因
"""

import asyncio
import sys
import os
from urllib.parse import urlencode, quote

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.async_executor import AsyncExecutor
from utils.device_manager import DeviceInfo

class AsyncInternalDebugger:
    """异步执行器内部调试器"""
    
    def __init__(self):
        self.debug_logs = []
    
    def log(self, message):
        """记录调试日志"""
        print(f"[DEBUG] {message}")
        self.debug_logs.append(message)
    
    async def debug_async_internal(self, device_ip):
        """调试异步执行器内部请求构造"""
        print(f"\n=== 调试异步执行器内部请求构造 - 设备 {device_ip} ===")
        
        # 创建设备信息
        device = DeviceInfo(
            index=0,
            ip=device_ip,
            port="80",
            username="admin",
            password="Zxkj@8787558"
        )
        
        # 创建异步执行器并启用调试
        executor = AsyncExecutor()
        
        # 测试命令
        command = {
            "action": "setConfig",
            "param": {
                "VideoWidget": [{
                    "Name": "VideoWidget",
                    "VideoWidgetTitle": {
                        "enabled": "true",
                        "text": "Test Title"
                    }
                }]
            }
        }
        
        # 分析URL构造过程
        await self.analyze_url_construction(device, command)
        
        # 分析认证处理过程
        await self.analyze_auth_processing(device, command, executor)
        
        # 测试修复后的URL构造
        await self.test_fixed_url_construction(device, command)
    
    async def analyze_url_construction(self, device, command):
        """分析URL构造过程"""
        print(f"\n1. URL构造分析:")
        
        # 基础URL
        base_url = f"http://{device.ip}:{device.port}"
        cgi_url = f"{base_url}/cgi-bin/configManager.cgi"
        
        print(f"   基础URL: {base_url}")
        print(f"   CGI端点: {cgi_url}")
        
        # 分析命令参数
        print(f"   命令参数: {command}")
        
        # 尝试不同的URL编码方式
        await self.test_different_encodings(cgi_url, command)
    
    async def test_different_encodings(self, base_url, command):
        """测试不同的URL编码方式"""
        print(f"\n2. URL编码测试:")
        
        # 方法1: 直接使用urlencode
        try:
            params = {
                "action": "setConfig",
                "VideoWidget": [{
                    "Name": "VideoWidget",
                    "VideoWidgetTitle": {
                        "enabled": "true",
                        "text": "Test Title"
                    }
                }]
            }
            
            query_string = urlencode(params, doseq=True)
            url1 = f"{base_url}?{query_string}"
            print(f"   方法1 (urlencode): {url1}")
            
        except Exception as e:
            print(f"   方法1 错误: {e}")
        
        # 方法2: 手动构造参数
        try:
            # 这是异步执行器中可能使用的方式
            param_str = "action=setConfig&VideoWidget[0][Name]=VideoWidget&VideoWidget[0][VideoWidgetTitle][enabled]=true&VideoWidget[0][VideoWidgetTitle][text]=Test Title"
            url2 = f"{base_url}?{param_str}"
            print(f"   方法2 (手动构造): {url2}")
            
        except Exception as e:
            print(f"   方法2 错误: {e}")
        
        # 方法3: 使用JSON格式参数
        try:
            import json
            json_params = json.dumps(command['param'])
            # 需要对JSON字符串进行URL编码
            encoded_json = quote(json_params)
            url3 = f"{base_url}?action=setConfig&param={encoded_json}"
            print(f"   方法3 (JSON参数): {url3}")
            
        except Exception as e:
            print(f"   方法3 错误: {e}")
    
    async def analyze_auth_processing(self, device, command, executor):
        """分析认证处理过程"""
        print(f"\n3. 认证处理分析:")
        
        # 检查异步执行器中的认证处理函数
        try:
            # 模拟异步执行器的认证处理过程
            base_url = f"http://{device.ip}:{device.port}"
            cgi_url = f"{base_url}/cgi-bin/configManager.cgi"
            
            # 构造参数
            params = {
                "action": "setConfig",
                "VideoWidget": [{
                    "Name": "VideoWidget",
                    "VideoWidgetTitle": {
                        "enabled": "true",
                        "text": "Test Title"
                    }
                }]
            }
            
            query_string = urlencode(params, doseq=True)
            full_url = f"{cgi_url}?{query_string}"
            
            print(f"   完整URL: {full_url}")
            print(f"   用户名: {device.username}")
            print(f"   密码: {device.password}")
            
            # 测试认证头构造
            await self.test_auth_header_construction(full_url, device.username, device.password)
            
        except Exception as e:
            print(f"   认证处理错误: {e}")
            import traceback
            traceback.print_exc()
    
    async def test_auth_header_construction(self, url, username, password):
        """测试认证头构造"""
        import aiohttp
        
        try:
            # 先获取认证要求
            async with aiohttp.ClientSession() as session:
                async with session.get(url, ssl=False) as response:
                    www_auth = response.headers.get('WWW-Authenticate', '')
                    print(f"   认证要求: {www_auth}")
                    
                    if response.status == 401 and 'Digest' in www_auth:
                        # 解析认证信息
                        realm = self.extract_value(www_auth, 'realm')
                        nonce = self.extract_value(www_auth, 'nonce')
                        qop = self.extract_value(www_auth, 'qop')
                        
                        print(f"   Realm: {realm}")
                        print(f"   Nonce: {nonce}")
                        print(f"   QOP: {qop}")
                        
                        # 测试异步执行器中的认证头构造
                        auth_header = self.build_digest_header_similar_to_async(
                            username, password, 'GET', url, realm, nonce, qop
                        )
                        
                        print(f"   构造的认证头: {auth_header}")
                        
                        # 发送认证请求
                        headers = {'Authorization': auth_header}
                        async with session.get(url, headers=headers, ssl=False) as auth_response:
                            print(f"   认证响应状态: {auth_response.status}")
                            
        except Exception as e:
            print(f"   认证头构造错误: {e}")
    
    def build_digest_header_similar_to_async(self, username, password, method, uri, realm, nonce, qop):
        """模拟异步执行器中的认证头构造"""
        import hashlib
        
        # 这是异步执行器中可能使用的算法
        ha1 = hashlib.md5(f"{username}:{realm}:{password}".encode()).hexdigest()
        ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()
        
        # 注意：这里可能有URI编码差异
        response = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
        
        auth_header = f'Digest username="{username}", realm="{realm}", nonce="{nonce}", uri="{uri}", response="{response}"'
        
        if qop:
            auth_header += f', qop={qop}'
            
        return auth_header
    
    def extract_value(self, auth_header, key):
        """从认证头中提取值"""
        import re
        pattern = f'{key}="([^"]*)"'
        match = re.search(pattern, auth_header)
        return match.group(1) if match else ""
    
    async def test_fixed_url_construction(self, device, command):
        """测试修复后的URL构造"""
        print(f"\n4. 修复方案测试:")
        
        # 方案1: 使用更简单的参数格式
        base_url = f"http://{device.ip}:{device.port}/cgi-bin/configManager.cgi"
        
        # 简化参数
        simple_params = "action=setConfig&name=VideoWidget&VideoWidgetTitle.enabled=true&VideoWidgetTitle.text=Test Title"
        simple_url = f"{base_url}?{simple_params}"
        
        print(f"   简化参数URL: {simple_url}")
        
        # 测试简化URL
        await self.test_url_with_requests(simple_url, device.username, device.password)
    
    async def test_url_with_requests(self, url, username, password):
        """使用requests测试URL"""
        import requests
        from requests.auth import HTTPDigestAuth
        
        try:
            auth = HTTPDigestAuth(username, password)
            response = requests.get(url, auth=auth, verify=False, timeout=5)
            
            print(f"   URL测试结果: 状态码 {response.status_code}")
            if response.status_code == 200:
                print(f"   成功! 响应: {response.text}")
            else:
                print(f"   失败! 响应头: {dict(response.headers)}")
                
        except Exception as e:
            print(f"   URL测试错误: {e}")

async def main():
    """主函数"""
    debugger = AsyncInternalDebugger()
    
    # 测试设备IP
    test_ip = "10.17.1.11"
    
    print("=" * 60)
    print("异步执行器内部请求构造调试")
    print("=" * 60)
    
    # 调试内部请求构造
    await debugger.debug_async_internal(test_ip)
    
    print("\n" + "=" * 60)
    print("调试完成")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())