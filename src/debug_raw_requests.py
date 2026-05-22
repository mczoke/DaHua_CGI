#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试原始请求构造问题
打印异步配置过程中的原始请求信息，分析401错误原因
"""

import asyncio
import aiohttp
import sys
import os
from urllib.parse import urlencode

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.async_executor import AsyncExecutor
from utils.device_manager import DeviceInfo

class RequestDebugger:
    """请求调试器"""
    
    def __init__(self):
        self.raw_requests = []
    
    async def debug_raw_request(self, device_ip, port="80", username="admin", password="Zxkj@8787558"):
        """调试单个设备的原始请求"""
        print(f"\n=== 调试设备 {device_ip} 的原始请求 ===")
        
        # 创建设备信息
        device = DeviceInfo(
            index=0,
            ip=device_ip,
            port=port,
            username=username,
            password=password
        )
        
        # 创建异步执行器
        executor = AsyncExecutor()
        
        # 测试命令：设置视频部件标题
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
        
        print(f"\n1. 命令信息:")
        print(f"   设备: {device.ip}:{device.port}")
        print(f"   用户名: {device.username}")
        print(f"   密码: {device.password}")
        print(f"   命令: {command}")
        
        # 构造URL
        base_url = f"http://{device.ip}:{device.port}"
        cgi_url = f"{base_url}/cgi-bin/configManager.cgi"
        
        print(f"\n2. URL构造信息:")
        print(f"   基础URL: {base_url}")
        print(f"   CGI端点: {cgi_url}")
        
        # 构造查询参数
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
        
        # 将参数转换为URL编码格式
        query_string = urlencode(params, doseq=True)
        full_url = f"{cgi_url}?{query_string}"
        
        print(f"\n3. 完整URL构造:")
        print(f"   查询参数: {params}")
        print(f"   URL编码: {query_string}")
        print(f"   完整URL: {full_url}")
        
        # 测试不同的认证方式
        await self.test_auth_methods(device, full_url, command)
    
    async def test_auth_methods(self, device, url, command):
        """测试不同的认证方式"""
        print(f"\n4. 认证方式测试:")
        
        # 方法1: 使用aiohttp内置认证
        print(f"\n   方法1: aiohttp内置认证")
        await self.test_aiohttp_auth(device, url, command)
        
        # 方法2: 手动构造认证头
        print(f"\n   方法2: 手动构造认证头")
        await self.test_manual_auth(device, url, command)
        
        # 方法3: 使用requests库（同步）
        print(f"\n   方法3: requests库同步测试")
        await self.test_requests_auth(device, url, command)
    
    async def test_aiohttp_auth(self, device, url, command):
        """测试aiohttp内置认证"""
        try:
            auth = aiohttp.BasicAuth(device.username, device.password)
            
            print(f"      认证类型: BasicAuth")
            print(f"      用户名: {device.username}")
            print(f"      密码: {device.password}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, auth=auth, ssl=False) as response:
                    print(f"      响应状态: {response.status}")
                    print(f"      响应头: {dict(response.headers)}")
                    
                    if response.status == 401:
                        www_auth = response.headers.get('WWW-Authenticate', '')
                        print(f"      认证要求: {www_auth}")
                    else:
                        text = await response.text()
                        print(f"      响应内容: {text[:200]}")
                        
        except Exception as e:
            print(f"      错误: {str(e)}")
    
    async def test_manual_auth(self, device, url, command):
        """测试手动构造认证头"""
        try:
            # 先发送不带认证的请求获取认证要求
            async with aiohttp.ClientSession() as session:
                async with session.get(url, ssl=False) as response:
                    www_auth = response.headers.get('WWW-Authenticate', '')
                    print(f"      认证要求头: {www_auth}")
                    
                    if response.status == 401 and 'Digest' in www_auth:
                        # 解析Digest认证信息
                        realm = self.extract_value(www_auth, 'realm')
                        nonce = self.extract_value(www_auth, 'nonce')
                        qop = self.extract_value(www_auth, 'qop')
                        
                        print(f"      Realm: {realm}")
                        print(f"      Nonce: {nonce}")
                        print(f"      QOP: {qop}")
                        
                        # 构造Digest认证头
                        auth_header = self.build_digest_header(
                            device.username, device.password, 
                            'GET', url, realm, nonce, qop
                        )
                        
                        print(f"      构造的认证头: {auth_header}")
                        
                        # 发送带认证的请求
                        headers = {'Authorization': auth_header}
                        async with session.get(url, headers=headers, ssl=False) as auth_response:
                            print(f"      认证响应状态: {auth_response.status}")
                            print(f"      认证响应头: {dict(auth_response.headers)}")
                            
                    else:
                        print(f"      响应状态: {response.status}")
                        
        except Exception as e:
            print(f"      错误: {str(e)}")
    
    async def test_requests_auth(self, device, url, command):
        """使用requests库测试（同步）"""
        import requests
        from requests.auth import HTTPDigestAuth
        
        try:
            # 测试Digest认证
            auth = HTTPDigestAuth(device.username, device.password)
            
            print(f"      认证类型: HTTPDigestAuth")
            print(f"      用户名: {device.username}")
            print(f"      密码: {device.password}")
            
            response = requests.get(url, auth=auth, verify=False, timeout=5)
            
            print(f"      响应状态: {response.status_code}")
            print(f"      响应头: {dict(response.headers)}")
            
            if response.status_code == 401:
                www_auth = response.headers.get('WWW-Authenticate', '')
                print(f"      认证要求: {www_auth}")
            else:
                print(f"      响应内容: {response.text[:200]}")
                
        except Exception as e:
            print(f"      错误: {str(e)}")
    
    def extract_value(self, auth_header, key):
        """从认证头中提取值"""
        import re
        pattern = f'{key}="([^"]*)"'
        match = re.search(pattern, auth_header)
        return match.group(1) if match else ""
    
    def build_digest_header(self, username, password, method, uri, realm, nonce, qop):
        """构造Digest认证头"""
        import hashlib
        
        # HA1 = MD5(username:realm:password)
        ha1 = hashlib.md5(f"{username}:{realm}:{password}".encode()).hexdigest()
        
        # HA2 = MD5(method:uri)
        ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()
        
        # Response = MD5(HA1:nonce:HA2)
        response = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
        
        auth_header = f'Digest username="{username}", realm="{realm}", nonce="{nonce}", uri="{uri}", response="{response}"'
        
        if qop:
            auth_header += f', qop={qop}'
            
        return auth_header
    
    async def debug_async_executor(self, device_ip):
        """调试异步执行器的原始请求"""
        print(f"\n=== 调试异步执行器对设备 {device_ip} 的请求 ===")
        
        # 创建设备信息
        device = DeviceInfo(
            index=0,
            ip=device_ip,
            port="80",
            username="admin",
            password="Zxkj@8787558"
        )
        
        # 创建异步执行器
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
        
        # 启用详细日志
        executor.enable_debug_logging = True
        
        try:
            # 执行异步命令
            result = await executor.send_command_async(device, command)
            print(f"执行结果: {result}")
            
        except Exception as e:
            print(f"执行错误: {str(e)}")
            import traceback
            traceback.print_exc()

async def main():
    """主函数"""
    debugger = RequestDebugger()
    
    # 测试设备IP
    test_ip = "10.17.1.11"
    
    print("=" * 60)
    print("原始请求调试工具")
    print("=" * 60)
    
    # 调试原始请求构造
    await debugger.debug_raw_request(test_ip)
    
    print("\n" + "=" * 60)
    print("异步执行器调试")
    print("=" * 60)
    
    # 调试异步执行器
    await debugger.debug_async_executor(test_ip)
    
    print("\n" + "=" * 60)
    print("调试完成")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())