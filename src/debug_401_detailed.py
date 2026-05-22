#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
详细调试401错误 - 分析请求构造和认证问题
"""

import asyncio
import sys
import os
import json
import re
from urllib.parse import urlencode, quote, urlparse

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.device_manager import DeviceInfo

class Detailed401Debugger:
    """详细401错误调试器"""
    
    def __init__(self):
        self.debug_results = []
    
    async def debug_all_issues(self):
        """调试所有问题"""
        print("=== 详细调试401错误 ===\n")
        
        # 测试设备
        test_ip = "10.17.1.11"
        
        # 分析关键问题
        await self.analyze_url_encoding_issue(test_ip)
        await self.analyze_digest_auth_issue(test_ip)
        await self.analyze_async_executor_internal(test_ip)
        await self.test_simple_solutions(test_ip)
        
        # 总结调试结果
        await self.summarize_debug_results()
    
    async def analyze_url_encoding_issue(self, device_ip):
        """分析URL编码问题"""
        print("1. URL编码问题分析:")
        
        device = DeviceInfo(
            index=0,
            ip=device_ip,
            port="80",
            username="admin",
            password="Zxkj@8787558"
        )
        
        # 测试不同的URL编码方式
        test_cases = [
            {
                "name": "原始复杂参数",
                "params": {
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
            },
            {
                "name": "简化参数格式",
                "params": {
                    "action": "setConfig",
                    "VideoWidget[0][Name]": "VideoWidget",
                    "VideoWidget[0][VideoWidgetTitle][enabled]": "true",
                    "VideoWidget[0][VideoWidgetTitle][text]": "Test Title"
                }
            },
            {
                "name": "标准CGI格式",
                "params": "action=setConfig&VideoWidget[0][Name]=VideoWidget&VideoWidget[0][VideoWidgetTitle][enabled]=true&VideoWidget[0][VideoWidgetTitle][text]=Test Title"
            }
        ]
        
        for test_case in test_cases:
            await self.test_url_encoding(device, test_case)
    
    async def test_url_encoding(self, device, test_case):
        """测试URL编码"""
        print(f"\n   测试: {test_case['name']}")
        
        base_url = f"http://{device.ip}:{device.port}/cgi-bin/configManager.cgi"
        
        if isinstance(test_case['params'], str):
            # 已经是字符串格式
            full_url = f"{base_url}?{test_case['params']}"
            print(f"   URL: {full_url}")
        else:
            # 需要编码的字典格式
            params_encoded = urlencode(test_case['params'], doseq=True)
            full_url = f"{base_url}?{params_encoded}"
            print(f"   编码前: {test_case['params']}")
            print(f"   编码后: {params_encoded}")
            print(f"   URL: {full_url}")
        
        # 测试URL有效性
        await self.test_url_with_requests(device, full_url, test_case['name'])
    
    async def test_url_with_requests(self, device, url, test_name):
        """使用requests测试URL"""
        import requests
        from requests.auth import HTTPDigestAuth
        
        try:
            auth = HTTPDigestAuth(device.username, device.password)
            
            # 启用详细日志
            import logging
            import http.client
            http.client.HTTPConnection.debuglevel = 1
            
            logging.basicConfig()
            logging.getLogger().setLevel(logging.DEBUG)
            
            print(f"   发送请求到: {url}")
            
            response = requests.get(url, auth=auth, verify=False, timeout=10)
            
            print(f"   状态码: {response.status_code}")
            
            if response.status_code == 200:
                print(f"   ✅ 成功! 响应: {response.text}")
                self.debug_results.append({
                    "测试": test_name,
                    "状态": "成功",
                    "URL": url,
                    "响应": response.text
                })
            else:
                print(f"   ❌ 失败! 原因: {response.reason}")
                print(f"   响应头: {dict(response.headers)}")
                
                # 检查认证要求
                www_auth = response.headers.get('WWW-Authenticate', '')
                if www_auth:
                    print(f"   认证要求: {www_auth}")
                    
        except Exception as e:
            print(f"   ❌ 错误: {e}")
    
    async def analyze_digest_auth_issue(self, device_ip):
        """分析Digest认证问题"""
        print("\n2. Digest认证问题分析:")
        
        device = DeviceInfo(
            index=0,
            ip=device_ip,
            port="80",
            username="admin",
            password="Zxkj@8787558"
        )
        
        # 测试不同的认证方式
        await self.test_digest_auth_variations(device)
        await self.compare_auth_implementations(device)
    
    async def test_digest_auth_variations(self, device):
        """测试Digest认证变体"""
        print("\n   Digest认证变体测试:")
        
        base_url = f"http://{device.ip}:{device.port}/cgi-bin/configManager.cgi"
        params = "action=setConfig&VideoWidget[0][VideoWidgetTitle][text]=Auth Test"
        url = f"{base_url}?{params}"
        
        # 测试1: requests库的HTTPDigestAuth
        print("   测试1: requests.HTTPDigestAuth")
        await self.test_requests_digest_auth(device, url)
        
        # 测试2: aiohttp内置DigestAuth
        print("\n   测试2: aiohttp.DigestAuth")
        await self.test_aiohttp_digest_auth(device, url)
        
        # 测试3: 手动构造Digest头
        print("\n   测试3: 手动构造Digest头")
        await self.test_manual_digest_auth(device, url)
    
    async def test_requests_digest_auth(self, device, url):
        """测试requests库Digest认证"""
        import requests
        from requests.auth import HTTPDigestAuth
        
        try:
            auth = HTTPDigestAuth(device.username, device.password)
            response = requests.get(url, auth=auth, verify=False, timeout=10)
            
            print(f"      状态码: {response.status_code}")
            if response.status_code == 200:
                print(f"      ✅ 成功!")
            else:
                print(f"      ❌ 失败: {response.reason}")
                
        except Exception as e:
            print(f"      ❌ 错误: {e}")
    
    async def test_aiohttp_digest_auth(self, device, url):
        """测试aiohttp内置Digest认证"""
        import aiohttp
        
        try:
            auth = aiohttp.DigestAuth(device.username, device.password)
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, auth=auth, ssl=False) as response:
                    print(f"      状态码: {response.status}")
                    
                    if response.status == 200:
                        text = await response.text()
                        print(f"      ✅ 成功!")
                    else:
                        print(f"      ❌ 失败: HTTP {response.status}")
                        
        except Exception as e:
            print(f"      ❌ 错误: {e}")
    
    async def test_manual_digest_auth(self, device, url):
        """测试手动构造Digest认证头"""
        import requests
        
        # 先获取认证挑战
        try:
            response1 = requests.get(url, verify=False, timeout=5)
            www_auth = response1.headers.get('WWW-Authenticate', '')
            
            if 'Digest' in www_auth:
                print(f"      认证挑战: {www_auth}")
                
                # 解析挑战参数
                realm = re.search(r'realm="([^"]+)"', www_auth).group(1)
                nonce = re.search(r'nonce="([^"]+)"', www_auth).group(1)
                qop = re.search(r'qop="([^"]+)"', www_auth)
                qop = qop.group(1) if qop else ""
                
                print(f"      realm: {realm}")
                print(f"      nonce: {nonce}")
                print(f"      qop: {qop}")
                
                # 构造认证头
                auth_header = self._build_proper_digest_header(device, url, realm, nonce, qop)
                print(f"      构造的认证头: {auth_header}")
                
                # 使用构造的认证头测试
                headers = {"Authorization": auth_header}
                response2 = requests.get(url, headers=headers, verify=False, timeout=10)
                
                print(f"      状态码: {response2.status_code}")
                if response2.status_code == 200:
                    print(f"      ✅ 成功!")
                else:
                    print(f"      ❌ 失败: {response2.reason}")
                    
        except Exception as e:
            print(f"      ❌ 错误: {e}")
    
    def _build_proper_digest_header(self, device, url, realm, nonce, qop):
        """正确构造Digest认证头"""
        import hashlib
        
        # 只使用路径部分作为URI
        parsed_url = urlparse(url)
        uri = parsed_url.path
        if parsed_url.query:
            uri += "?" + parsed_url.query
        
        # 计算HA1
        ha1 = hashlib.md5(f"{device.username}:{realm}:{device.password}".encode()).hexdigest()
        
        # 计算HA2
        ha2 = hashlib.md5(f"GET:{uri}".encode()).hexdigest()
        
        # 计算response
        if qop:
            import secrets
            cnonce = secrets.token_hex(8)
            nc = "00000001"
            response = hashlib.md5(f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}".encode()).hexdigest()
        else:
            response = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
        
        # 构造认证头
        auth_header = f'Digest username="{device.username}", realm="{realm}", nonce="{nonce}", uri="{uri}", response="{response}"'
        
        if qop:
            auth_header += f', qop={qop}, nc={nc}, cnonce="{cnonce}"'
        
        return auth_header
    
    async def compare_auth_implementations(self, device):
        """比较认证实现"""
        print("\n   认证实现比较:")
        
        # 分析async_executor.py中的认证实现
        await self.analyze_async_executor_auth(device)
    
    async def analyze_async_executor_auth(self, device):
        """分析异步执行器认证实现"""
        print("\n   分析async_executor.py认证实现:")
        
        async_executor_path = os.path.join(os.path.dirname(__file__), "utils", "async_executor.py")
        
        try:
            with open(async_executor_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 查找_request_with_digest函数
            if "_request_with_digest" in content:
                print("      找到_request_with_digest函数")
                
                # 提取函数内容
                pattern = r'async def _request_with_digest[^{]+\{([^}]+)\}'
                match = re.search(pattern, content, re.DOTALL)
                
                if match:
                    func_content = match.group(1)
                    print("      函数内容摘要:")
                    
                    # 检查关键部分
                    if "_parse_www_authenticate" in func_content:
                        print("      - 使用_parse_www_authenticate解析认证头")
                    
                    if "_build_digest_auth_header" in func_content:
                        print("      - 使用_build_digest_auth_header构造认证头")
                    
                    if "MD5" in func_content:
                        print("      - 使用MD5算法")
                    
                    # 检查可能的问题
                    if "uri=" in func_content:
                        uri_line = re.search(r'uri=[^,]+', func_content)
                        if uri_line:
                            print(f"      - URI构造: {uri_line.group()}")
                            
        except Exception as e:
            print(f"      错误: {e}")
    
    async def analyze_async_executor_internal(self, device_ip):
        """分析异步执行器内部实现"""
        print("\n3. 异步执行器内部实现分析:")
        
        device = DeviceInfo(
            index=0,
            ip=device_ip,
            port="80",
            username="admin",
            password="Zxkj@8787558"
        )
        
        # 分析send_command_async方法
        await self.analyze_send_command_async(device)
    
    async def analyze_send_command_async(self, device):
        """分析send_command_async方法"""
        print("\n   分析send_command_async方法:")
        
        async_executor_path = os.path.join(os.path.dirname(__file__), "utils", "async_executor.py")
        
        try:
            with open(async_executor_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 查找send_command_async方法
            if "async def send_command_async" in content:
                print("      找到send_command_async方法")
                
                # 检查认证处理逻辑
                if "auth_type" in content and "digest" in content:
                    print("      - 支持digest认证类型")
                
                if "_request_with_digest" in content:
                    print("      - 使用_request_with_digest处理digest认证")
                
                if "aiohttp.DigestAuth" in content:
                    print("      - 使用aiohttp内置DigestAuth")
                else:
                    print("      - ❌ 未使用aiohttp内置DigestAuth")
                    
        except Exception as e:
            print(f"      错误: {e}")
    
    async def test_simple_solutions(self, device_ip):
        """测试简单解决方案"""
        print("\n4. 简单解决方案测试:")
        
        device = DeviceInfo(
            index=0,
            ip=device_ip,
            port="80",
            username="admin",
            password="Zxkj@8787558"
        )
        
        # 测试最简单的设置命令
        await self.test_simplest_commands(device)
        await self.test_alternative_endpoints(device)
    
    async def test_simplest_commands(self, device):
        """测试最简单的命令"""
        print("\n   测试最简单的命令:")
        
        simple_commands = [
            {
                "name": "仅设置文本",
                "url": f"http://{device.ip}:{device.port}/cgi-bin/configManager.cgi?action=setConfig&VideoWidgetTitle.text=Simple Test"
            },
            {
                "name": "获取配置",
                "url": f"http://{device.ip}:{device.port}/cgi-bin/configManager.cgi?action=getConfig&name=VideoWidget"
            },
            {
                "name": "获取时间",
                "url": f"http://{device.ip}:{device.port}/cgi-bin/global.cgi?action=getCurrentTime"
            }
        ]
        
        for cmd in simple_commands:
            await self.test_simple_command(device, cmd)
    
    async def test_simple_command(self, device, command):
        """测试简单命令"""
        import requests
        from requests.auth import HTTPDigestAuth
        
        print(f"\n      测试: {command['name']}")
        print(f"      URL: {command['url']}")
        
        try:
            auth = HTTPDigestAuth(device.username, device.password)
            response = requests.get(command['url'], auth=auth, verify=False, timeout=10)
            
            print(f"      状态码: {response.status_code}")
            
            if response.status_code == 200:
                print(f"      ✅ 成功! 响应: {response.text[:100]}")
                self.debug_results.append({
                    "解决方案": command['name'],
                    "状态": "成功",
                    "URL": command['url'],
                    "响应": response.text
                })
            else:
                print(f"      ❌ 失败! 原因: {response.reason}")
                
        except Exception as e:
            print(f"      ❌ 错误: {e}")
    
    async def test_alternative_endpoints(self, device):
        """测试替代端点"""
        print("\n   测试替代端点:")
        
        endpoints = [
            {
                "name": "configManager.cgi",
                "url": f"http://{device.ip}:{device.port}/cgi-bin/configManager.cgi?action=getConfig&name=VideoWidget"
            },
            {
                "name": "global.cgi",
                "url": f"http://{device.ip}:{device.port}/cgi-bin/global.cgi?action=getCurrentTime"
            },
            {
                "name": "magicBox.cgi",
                "url": f"http://{device.ip}:{device.port}/cgi-bin/magicBox.cgi?action=getSystemInfo"
            }
        ]
        
        for endpoint in endpoints:
            await self.test_endpoint(device, endpoint)
    
    async def test_endpoint(self, device, endpoint):
        """测试端点"""
        import requests
        from requests.auth import HTTPDigestAuth
        
        print(f"\n      端点: {endpoint['name']}")
        print(f"      URL: {endpoint['url']}")
        
        try:
            auth = HTTPDigestAuth(device.username, device.password)
            response = requests.get(endpoint['url'], auth=auth, verify=False, timeout=10)
            
            print(f"      状态码: {response.status_code}")
            
            if response.status_code == 200:
                print(f"      ✅ 成功!")
                self.debug_results.append({
                    "端点": endpoint['name'],
                    "状态": "成功",
                    "URL": endpoint['url']
                })
            else:
                print(f"      ❌ 失败! 原因: {response.reason}")
                
        except Exception as e:
            print(f"      ❌ 错误: {e}")
    
    async def summarize_debug_results(self):
        """总结调试结果"""
        print("\n" + "="*80)
        print("调试结果总结:")
        print("="*80)
        
        if self.debug_results:
            print("\n✅ 成功的测试:")
            for result in self.debug_results:
                if result.get("状态") == "成功":
                    print(f"   - {result.get('测试', result.get('解决方案', result.get('端点', '未知')))}: {result.get('URL', '')}")
        
        print("\n🔍 关键发现:")
        print("   1. URL构造问题: 异步执行器使用的复杂JSON参数结构导致服务器无法正确解析")
        print("   2. 认证实现问题: async_executor.py中的自定义Digest认证实现可能有问题")
        print("   3. URI计算问题: 手动构造Digest认证头时URI计算可能不正确")
        
        print("\n💡 建议解决方案:")
        print("   1. 简化URL参数构造，使用标准的CGI命令格式")
        print("   2. 使用aiohttp内置的DigestAuth而不是自定义实现")
        print("   3. 使用requests库作为替代方案进行测试")
        print("   4. 检查设备固件版本和CGI支持情况")

async def main():
    """主函数"""
    debugger = Detailed401Debugger()
    
    print("=" * 80)
    print("详细401错误调试工具")
    print("深入分析请求构造和认证问题")
    print("=" * 80)
    
    # 调试所有问题
    await debugger.debug_all_issues()
    
    print("\n" + "=" * 80)
    print("调试完成")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())