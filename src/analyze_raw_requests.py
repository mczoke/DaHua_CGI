#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析原始请求和响应，诊断401错误
打印详细的请求构造和认证信息
"""

import asyncio
import sys
import os
import json
from urllib.parse import urlencode, quote

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.device_manager import DeviceInfo

class RequestAnalyzer:
    """请求分析器"""
    
    def __init__(self):
        self.analysis_results = []
    
    async def analyze_all_requests(self):
        """分析所有请求"""
        print("=== 分析原始请求和401错误 ===\n")
        
        # 测试设备
        test_ip = "10.17.1.11"
        
        # 分析不同请求方式
        await self.analyze_async_executor_requests(test_ip)
        await self.analyze_manual_requests(test_ip)
        await self.analyze_requests_library(test_ip)
        
        # 总结分析结果
        await self.summarize_findings()
    
    async def analyze_async_executor_requests(self, device_ip):
        """分析异步执行器请求"""
        print("1. 分析异步执行器请求构造:")
        
        try:
            from utils.async_executor import AsyncExecutor
            
            device = DeviceInfo(
                index=0,
                ip=device_ip,
                port="80",
                username="admin",
                password="Zxkj@8787558"
            )
            
            # 构造命令
            command = {
                "action": "setConfig",
                "param": {
                    "VideoWidget": [
                        {
                            "Name": "VideoWidget",
                            "VideoWidgetTitle": {
                                "enabled": True,
                                "text": "Test Title"
                            }
                        }
                    ]
                }
            }
            
            print("   命令结构:")
            print(f"   {json.dumps(command, indent=2, ensure_ascii=False)}")
            
            # 分析URL构造
            await self.analyze_url_construction(device, command)
            
            # 测试异步执行器
            await self.test_async_executor(device, command)
            
        except Exception as e:
            print(f"   错误: {e}")
    
    async def analyze_url_construction(self, device, command):
        """分析URL构造"""
        print("\n   URL构造分析:")
        
        # 分析不同的URL构造方式
        base_url = f"http://{device.ip}:{device.port}/cgi-bin/configManager.cgi"
        
        # 方式1: 使用urlencode
        params1 = urlencode(command, doseq=True)
        url1 = f"{base_url}?{params1}"
        print(f"   方式1 (urlencode): {url1[:200]}...")
        
        # 方式2: 手动构造简化参数
        params2 = self._build_simple_params(command)
        url2 = f"{base_url}?{params2}"
        print(f"   方式2 (简化参数): {url2}")
        
        # 方式3: 标准大华格式
        params3 = "action=setConfig&VideoWidget[0][Name]=VideoWidget&VideoWidget[0][VideoWidgetTitle][enabled]=true&VideoWidget[0][VideoWidgetTitle][text]=Test Title"
        url3 = f"{base_url}?{params3}"
        print(f"   方式3 (标准格式): {url3}")
    
    def _build_simple_params(self, command):
        """构造简化参数"""
        param = command.get("param", {})
        params = ["action=setConfig"]
        
        for key, value in param.items():
            if isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        for sub_key, sub_value in item.items():
                            if isinstance(sub_value, dict):
                                for sub_sub_key, sub_sub_value in sub_value.items():
                                    params.append(f"{key}[{i}][{sub_key}][{sub_sub_key}]={sub_sub_value}")
                            else:
                                params.append(f"{key}[{i}][{sub_key}]={sub_value}")
            else:
                params.append(f"{key}={value}")
        
        return "&".join(params)
    
    async def test_async_executor(self, device, command):
        """测试异步执行器"""
        print("\n   异步执行器测试:")
        
        try:
            from utils.async_executor import AsyncExecutor
            
            executor = AsyncExecutor()
            
            # 启用详细日志
            import logging
            logging.basicConfig(level=logging.DEBUG)
            
            # 测试异步执行
            success, response, status, data, error = await executor.send_command_async(device, command)
            
            print(f"   结果: 成功={success}, 状态={status}, 错误={error}")
            print(f"   响应: {response}")
            
        except Exception as e:
            print(f"   错误: {e}")
    
    async def analyze_manual_requests(self, device_ip):
        """分析手动构造的请求"""
        print("\n2. 分析手动请求构造:")
        
        device = DeviceInfo(
            index=0,
            ip=device_ip,
            port="80",
            username="admin",
            password="Zxkj@8787558"
        )
        
        # 测试不同的认证方式
        await self.test_digest_auth_manual(device)
        await self.test_basic_auth(device)
        await self.test_no_auth(device)
    
    async def test_digest_auth_manual(self, device):
        """测试手动Digest认证"""
        print("\n   手动Digest认证测试:")
        
        import aiohttp
        import hashlib
        
        base_url = f"http://{device.ip}:{device.port}/cgi-bin/configManager.cgi"
        params = "action=setConfig&VideoWidget[0][VideoWidgetTitle][text]=Manual Test"
        url = f"{base_url}?{params}"
        
        print(f"   请求URL: {url}")
        print(f"   用户名: {device.username}")
        print(f"   密码: {device.password}")
        
        try:
            # 使用aiohttp内置Digest认证
            auth = aiohttp.DigestAuth(device.username, device.password)
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, auth=auth, ssl=False) as response:
                    print(f"   状态码: {response.status}")
                    print(f"   响应头: {dict(response.headers)}")
                    
                    if response.status == 200:
                        text = await response.text()
                        print(f"   响应内容: {text}")
                    else:
                        # 检查认证头
                        www_auth = response.headers.get('WWW-Authenticate', '')
                        print(f"   认证要求: {www_auth}")
                        
        except Exception as e:
            print(f"   错误: {e}")
    
    async def test_basic_auth(self, device):
        """测试Basic认证"""
        print("\n   Basic认证测试:")
        
        import aiohttp
        import base64
        
        base_url = f"http://{device.ip}:{device.port}/cgi-bin/configManager.cgi"
        params = "action=getConfig&name=VideoWidget"
        url = f"{base_url}?{params}"
        
        # 手动构造Basic认证头
        credentials = base64.b64encode(f"{device.username}:{device.password}".encode()).decode()
        headers = {"Authorization": f"Basic {credentials}"}
        
        print(f"   请求URL: {url}")
        print(f"   认证头: {headers['Authorization'][:50]}...")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, ssl=False) as response:
                    print(f"   状态码: {response.status}")
                    print(f"   响应头: {dict(response.headers)}")
                    
        except Exception as e:
            print(f"   错误: {e}")
    
    async def test_no_auth(self, device):
        """测试无认证请求"""
        print("\n   无认证请求测试:")
        
        import aiohttp
        
        base_url = f"http://{device.ip}:{device.port}/cgi-bin/configManager.cgi"
        params = "action=getConfig&name=VideoWidget"
        url = f"{base_url}?{params}"
        
        print(f"   请求URL: {url}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, ssl=False) as response:
                    print(f"   状态码: {response.status}")
                    print(f"   响应头: {dict(response.headers)}")
                    
                    # 检查认证要求
                    www_auth = response.headers.get('WWW-Authenticate', '')
                    if www_auth:
                        print(f"   服务器认证要求: {www_auth}")
                        
        except Exception as e:
            print(f"   错误: {e}")
    
    async def analyze_requests_library(self, device_ip):
        """分析requests库请求"""
        print("\n3. 分析requests库请求:")
        
        device = DeviceInfo(
            index=0,
            ip=device_ip,
            port="80",
            username="admin",
            password="Zxkj@8787558"
        )
        
        # 测试requests库的不同认证方式
        await self.test_requests_digest_auth(device)
        await self.test_requests_with_raw_headers(device)
    
    async def test_requests_digest_auth(self, device):
        """测试requests库的Digest认证"""
        print("\n   requests库Digest认证测试:")
        
        import requests
        from requests.auth import HTTPDigestAuth
        
        base_url = f"http://{device.ip}:{device.port}/cgi-bin/configManager.cgi"
        params = "action=setConfig&VideoWidget[0][VideoWidgetTitle][text]=Requests Test"
        url = f"{base_url}?{params}"
        
        print(f"   请求URL: {url}")
        print(f"   用户名: {device.username}")
        print(f"   密码: {device.password}")
        
        try:
            # 启用详细日志
            import logging
            import http.client
            http.client.HTTPConnection.debuglevel = 1
            
            # 配置日志
            logging.basicConfig()
            logging.getLogger().setLevel(logging.DEBUG)
            requests_log = logging.getLogger("requests.packages.urllib3")
            requests_log.setLevel(logging.DEBUG)
            requests_log.propagate = True
            
            auth = HTTPDigestAuth(device.username, device.password)
            response = requests.get(url, auth=auth, verify=False, timeout=10)
            
            print(f"   状态码: {response.status_code}")
            print(f"   响应头: {dict(response.headers)}")
            
            if response.status_code == 200:
                print(f"   响应内容: {response.text}")
            else:
                print(f"   错误信息: {response.reason}")
                
        except Exception as e:
            print(f"   错误: {e}")
    
    async def test_requests_with_raw_headers(self, device):
        """测试requests库带原始头信息"""
        print("\n   requests库原始头信息测试:")
        
        import requests
        
        base_url = f"http://{device.ip}:{device.port}/cgi-bin/configManager.cgi"
        params = "action=setConfig&VideoWidget[0][VideoWidgetTitle][text]=Raw Headers Test"
        url = f"{base_url}?{params}"
        
        # 第一次请求获取认证信息
        print("   第一次请求（获取认证要求）:")
        try:
            response1 = requests.get(url, verify=False, timeout=5)
            print(f"   状态码: {response1.status_code}")
            
            www_auth = response1.headers.get('WWW-Authenticate', '')
            print(f"   认证要求: {www_auth}")
            
            # 解析认证信息
            if 'Digest' in www_auth:
                await self.parse_digest_challenge(www_auth, device, url)
                
        except Exception as e:
            print(f"   错误: {e}")
    
    async def parse_digest_challenge(self, www_auth, device, url):
        """解析Digest认证挑战"""
        print("\n   Digest认证挑战解析:")
        
        # 解析realm, nonce, qop等参数
        import re
        
        realm_match = re.search(r'realm="([^"]+)"', www_auth)
        nonce_match = re.search(r'nonce="([^"]+)"', www_auth)
        qop_match = re.search(r'qop="([^"]+)"', www_auth)
        
        realm = realm_match.group(1) if realm_match else ""
        nonce = nonce_match.group(1) if nonce_match else ""
        qop = qop_match.group(1) if qop_match else ""
        
        print(f"   realm: {realm}")
        print(f"   nonce: {nonce}")
        print(f"   qop: {qop}")
        
        # 手动构造Digest认证头
        auth_header = self._build_digest_header(device, url, realm, nonce, qop)
        print(f"   构造的认证头: {auth_header}")
        
        # 使用构造的认证头测试
        await self.test_with_custom_auth_header(device, url, auth_header)
    
    def _build_digest_header(self, device, url, realm, nonce, qop):
        """构造Digest认证头"""
        import hashlib
        
        # 计算HA1
        ha1 = hashlib.md5(f"{device.username}:{realm}:{device.password}".encode()).hexdigest()
        
        # 计算HA2
        ha2 = hashlib.md5(f"GET:{url}".encode()).hexdigest()
        
        # 计算response
        if qop:
            response = hashlib.md5(f"{ha1}:{nonce}:00000001:auth:{ha2}".encode()).hexdigest()
        else:
            response = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
        
        # 构造认证头
        auth_header = f'Digest username="{device.username}", realm="{realm}", nonce="{nonce}", uri="{url}", response="{response}"'
        
        if qop:
            auth_header += f', qop={qop}, nc=00000001, cnonce="testcnonce"'
        
        return auth_header
    
    async def test_with_custom_auth_header(self, device, url, auth_header):
        """使用自定义认证头测试"""
        import requests
        
        headers = {"Authorization": auth_header}
        
        print(f"   使用自定义认证头测试:")
        
        try:
            response = requests.get(url, headers=headers, verify=False, timeout=5)
            print(f"   状态码: {response.status_code}")
            print(f"   响应头: {dict(response.headers)}")
            
            if response.status_code == 200:
                print(f"   成功! 响应: {response.text}")
            else:
                print(f"   失败! 原因: {response.reason}")
                
        except Exception as e:
            print(f"   错误: {e}")
    
    async def summarize_findings(self):
        """总结发现的问题"""
        print("\n" + "="*60)
        print("问题总结:")
        print("="*60)
        
        print("\n1. URL构造问题:")
        print("   - 异步执行器使用的参数构造过于复杂")
        print("   - 嵌套的JSON结构可能导致服务器无法正确解析")
        print("   - 建议使用简化的参数格式")
        
        print("\n2. 认证问题:")
        print("   - 异步执行器的Digest认证实现可能有问题")
        print("   - 认证头构造可能不符合服务器要求")
        print("   - 建议使用aiohttp内置认证或requests库")
        
        print("\n3. 建议解决方案:")
        print("   - 简化URL参数构造")
        print("   - 使用标准的CGI命令格式")
        print("   - 使用requests库作为替代方案")
        print("   - 检查设备固件版本和CGI支持情况")

async def main():
    """主函数"""
    analyzer = RequestAnalyzer()
    
    print("=" * 60)
    print("原始请求分析工具")
    print("诊断401认证错误")
    print("=" * 60)
    
    # 分析所有请求
    await analyzer.analyze_all_requests()
    
    print("\n" + "=" * 60)
    print("分析完成")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())