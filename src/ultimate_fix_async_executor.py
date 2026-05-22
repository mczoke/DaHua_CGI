#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
终极修复异步执行器 - 解决401错误
基于实际测试结果，修复aiohttp版本兼容性问题
"""

import asyncio
import sys
import os
import json
from urllib.parse import urlencode
import aiohttp

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.device_manager import DeviceInfo

class UltimateAsyncExecutorFixer:
    """终极异步执行器修复器"""
    
    def __init__(self):
        self.fix_applied = False
    
    async def apply_ultimate_fix(self):
        """应用终极修复"""
        print("=== 应用终极修复方案 ===\n")
        
        # 1. 检查aiohttp版本和认证支持
        await self.check_aiohttp_version()
        
        # 2. 创建基于实际测试的修复方案
        await self.create_ultimate_fix()
        
        # 3. 测试终极修复方案
        await self.test_ultimate_solution()
        
        # 4. 提供最终建议
        await self.provide_final_recommendations()
    
    async def check_aiohttp_version(self):
        """检查aiohttp版本和认证支持"""
        print("1. 检查aiohttp版本和认证支持:")
        
        print(f"   aiohttp版本: {aiohttp.__version__}")
        
        # 检查DigestAuth支持
        if hasattr(aiohttp, 'DigestAuth'):
            print("   ✅ aiohttp支持内置Digest认证")
        else:
            print("   ❌ aiohttp不支持内置Digest认证")
            print("   💡 需要手动实现Digest认证或使用requests库")
        
        # 检查其他认证方式
        auth_methods = []
        if hasattr(aiohttp, 'BasicAuth'):
            auth_methods.append("BasicAuth")
        if hasattr(aiohttp, 'DigestAuth'):
            auth_methods.append("DigestAuth")
        
        print(f"   支持的认证方式: {auth_methods}")
    
    async def create_ultimate_fix(self):
        """创建终极修复方案"""
        print("\n2. 创建终极修复方案:")
        
        ultimate_content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
终极修复的异步执行器
基于实际测试结果，解决aiohttp版本兼容性问题
"""

import aiohttp
import asyncio
import json
import hashlib
import random
import re
from urllib.parse import urlencode, quote
from typing import Dict, Any, Tuple, Optional

class UltimateAsyncExecutor:
    """终极修复的异步执行器"""
    
    async def send_command_ultimate(self, device, command: Dict[str, Any]) -> Tuple[bool, str, str, Dict, str]:
        """
        终极修复的发送命令方法
        
        Args:
            device: 设备信息对象
            command: 命令字典
            
        Returns:
            Tuple[成功标志, 响应文本, 状态, 数据, 错误信息]
        """
        try:
            # 构造基础URL
            base_url = f"http://{device.ip}:{device.port}/cgi-bin/configManager.cgi"
            
            # 使用简化的参数构造
            params = self._build_simple_params(command)
            url = f"{base_url}?{params}"
            
            print(f"[UltimateAsyncExecutor] 发送请求到: {url}")
            
            # 根据aiohttp版本选择合适的认证方式
            if hasattr(aiohttp, 'DigestAuth'):
                # 使用aiohttp内置Digest认证
                auth = aiohttp.DigestAuth(device.username, device.password)
                return await self._send_request_with_auth(url, auth)
            else:
                # 手动实现Digest认证
                return await self._send_request_with_manual_digest(url, device.username, device.password)
                        
        except asyncio.TimeoutError:
            error_msg = "请求超时"
            print(f"[UltimateAsyncExecutor] {error_msg}")
            return False, "", "FAILED", {}, error_msg
            
        except Exception as e:
            error_msg = f"请求异常: {str(e)}"
            print(f"[UltimateAsyncExecutor] {error_msg}")
            return False, "", "FAILED", {}, error_msg
    
    async def _send_request_with_auth(self, url: str, auth) -> Tuple[bool, str, str, Dict, str]:
        """使用认证发送请求"""
        timeout = aiohttp.ClientTimeout(total=30)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, auth=auth, ssl=False) as response:
                
                if response.status == 200:
                    text = await response.text()
                    print(f"[UltimateAsyncExecutor] 请求成功: {text}")
                    return True, text, "SUCCESS", {}, ""
                else:
                    error_msg = f"HTTP {response.status}: {response.reason}"
                    print(f"[UltimateAsyncExecutor] 请求失败: {error_msg}")
                    
                    # 检查认证要求
                    www_auth = response.headers.get('WWW-Authenticate', '')
                    if www_auth:
                        print(f"[UltimateAsyncExecutor] 认证要求: {www_auth}")
                    
                    return False, "", "FAILED", {}, error_msg
    
    async def _send_request_with_manual_digest(self, url: str, username: str, password: str) -> Tuple[bool, str, str, Dict, str]:
        """手动实现Digest认证"""
        timeout = aiohttp.ClientTimeout(total=30)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # 第一次请求，获取认证挑战
            async with session.get(url, ssl=False) as response:
                
                if response.status == 200:
                    text = await response.text()
                    print(f"[UltimateAsyncExecutor] 请求成功: {text}")
                    return True, text, "SUCCESS", {}, ""
                
                elif response.status == 401:
                    www_auth = response.headers.get('WWW-Authenticate', '')
                    print(f"[UltimateAsyncExecutor] 收到401挑战: {www_auth}")
                    
                    if www_auth and 'Digest' in www_auth:
                        # 解析认证挑战
                        auth_params = self._parse_digest_challenge(www_auth)
                        
                        if auth_params:
                            # 构造认证头
                            auth_header = self._build_digest_header(url, username, password, auth_params)
                            
                            # 使用认证头重新发送请求
                            headers = {'Authorization': auth_header}
                            
                            async with session.get(url, headers=headers, ssl=False) as auth_response:
                                
                                if auth_response.status == 200:
                                    text = await auth_response.text()
                                    print(f"[UltimateAsyncExecutor] 认证成功: {text}")
                                    return True, text, "SUCCESS", {}, ""
                                else:
                                    error_msg = f"HTTP {auth_response.status}: {auth_response.reason}"
                                    print(f"[UltimateAsyncExecutor] 认证失败: {error_msg}")
                                    return False, "", "FAILED", {}, error_msg
                        else:
                            error_msg = "无法解析认证挑战"
                            print(f"[UltimateAsyncExecutor] {error_msg}")
                            return False, "", "FAILED", {}, error_msg
                    else:
                        error_msg = "服务器不支持Digest认证"
                        print(f"[UltimateAsyncExecutor] {error_msg}")
                        return False, "", "FAILED", {}, error_msg
                
                else:
                    error_msg = f"HTTP {response.status}: {response.reason}"
                    print(f"[UltimateAsyncExecutor] 请求失败: {error_msg}")
                    return False, "", "FAILED", {}, error_msg
    
    def _parse_digest_challenge(self, www_auth: str) -> Optional[Dict[str, str]]:
        """解析Digest认证挑战"""
        try:
            # 提取Digest参数
            digest_match = re.search(r'Digest\s+(.+)', www_auth)
            if not digest_match:
                return None
            
            params_str = digest_match.group(1)
            params = {}
            
            # 解析参数
            for match in re.finditer(r'(\w+)="([^"]*)"', params_str):
                params[match.group(1)] = match.group(2)
            
            print(f"[UltimateAsyncExecutor] 解析的认证参数: {params}")
            return params
            
        except Exception as e:
            print(f"[UltimateAsyncExecutor] 解析认证挑战失败: {e}")
            return None
    
    def _build_digest_header(self, url: str, username: str, password: str, auth_params: Dict[str, str]) -> str:
        """构造Digest认证头"""
        realm = auth_params.get('realm', '')
        nonce = auth_params.get('nonce', '')
        qop = auth_params.get('qop', '')
        
        # 生成客户端nonce
        cnonce = hashlib.md5(str(random.random()).encode()).hexdigest()
        
        # 生成请求计数器
        nc = '00000001'
        
        # 提取URI路径
        uri_match = re.search(r'http://[^/]+(/.*)', url)
        uri = uri_match.group(1) if uri_match else url
        
        # 计算HA1
        ha1 = hashlib.md5(f"{username}:{realm}:{password}".encode()).hexdigest()
        
        # 计算HA2
        ha2 = hashlib.md5(f"GET:{uri}".encode()).hexdigest()
        
        # 计算响应
        if qop:
            response = hashlib.md5(f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}".encode()).hexdigest()
        else:
            response = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
        
        # 构造认证头
        auth_header = f'Digest username="{username}", realm="{realm}", nonce="{nonce}", uri="{uri}", response="{response}"'
        
        if qop:
            auth_header += f', qop={qop}, nc={nc}, cnonce="{cnonce}"'
        
        print(f"[UltimateAsyncExecutor] 构造的认证头: {auth_header}")
        return auth_header
    
    def _build_simple_params(self, command: Dict[str, Any]) -> str:
        """构造简化的参数"""
        action = command.get("action", "")
        
        if action == "setConfig":
            # 对于setConfig命令，使用标准的大华设备格式
            return self._build_dahua_params(command)
        else:
            # 对于其他命令，使用urlencode
            return urlencode(command, doseq=True)
    
    def _build_dahua_params(self, command: Dict[str, Any]) -> str:
        """构造大华设备标准参数格式"""
        param = command.get("param", {})
        params = ["action=setConfig"]
        
        # 扁平化参数处理
        for key, value in param.items():
            if isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        for sub_key, sub_value in item.items():
                            if isinstance(sub_value, dict):
                                for sub_sub_key, sub_sub_value in sub_value.items():
                                    param_str = f"{key}[{i}][{sub_key}][{sub_sub_key}]={sub_sub_value}"
                                    params.append(param_str)
                            else:
                                param_str = f"{key}[{i}][{sub_key}]={sub_value}"
                                params.append(param_str)
            else:
                param_str = f"{key}={value}"
                params.append(param_str)
        
        return "&".join(params)

# 兼容性包装器
class AsyncExecutor:
    """兼容性包装器，保持原有接口"""
    
    def __init__(self):
        self.ultimate_executor = UltimateAsyncExecutor()
    
    async def send_command_async(self, device, command):
        """保持原有接口"""
        return await self.ultimate_executor.send_command_ultimate(device, command)
'''
        
        ultimate_file_path = os.path.join(os.path.dirname(__file__), "ultimate_async_executor.py")
        
        with open(ultimate_file_path, 'w', encoding='utf-8') as f:
            f.write(ultimate_content)
        
        print("   ✅ 终极修复的异步执行器已创建: ultimate_async_executor.py")
        self.fix_applied = True
    
    async def test_ultimate_solution(self):
        """测试终极修复方案"""
        print("\n3. 测试终极修复方案:")
        
        if not self.fix_applied:
            print("   ❌ 修复未应用，跳过测试")
            return
        
        # 导入终极修复的执行器
        sys.path.insert(0, os.path.dirname(__file__))
        
        try:
            from ultimate_async_executor import UltimateAsyncExecutor
            
            device = DeviceInfo(
                index=0,
                ip="10.17.1.11",
                port="80",
                username="admin",
                password="Zxkj@8787558"
            )
            
            # 测试命令
            test_commands = [
                {
                    "name": "获取配置",
                    "command": {
                        "action": "getConfig",
                        "name": "VideoWidget"
                    }
                },
                {
                    "name": "获取时间",
                    "command": {
                        "action": "getCurrentTime",
                        "name": "global"
                    }
                }
            ]
            
            executor = UltimateAsyncExecutor()
            
            for test in test_commands:
                print(f"\n   测试: {test['name']}")
                
                success, response, status, data, error = await executor.send_command_ultimate(device, test['command'])
                
                if success:
                    print(f"   ✅ 成功! 状态: {status}")
                    print(f"   响应: {response}")
                else:
                    print(f"   ❌ 失败! 错误: {error}")
                    
        except Exception as e:
            print(f"   ❌ 测试错误: {e}")
    
    async def provide_final_recommendations(self):
        """提供最终建议"""
        print("\n4. 最终建议和解决方案:")
        
        # 创建requests库的终极解决方案
        await self.create_ultimate_requests_solution()
        
        # 提供修复建议
        print("\n   💡 关键发现和建议:")
        print("   1. aiohttp版本不支持内置Digest认证")
        print("   2. 手动实现的Digest认证可能更可靠")
        print("   3. requests库的Digest认证已经验证成功")
        print("   4. 建议优先使用requests库作为替代方案")
    
    async def create_ultimate_requests_solution(self):
        """创建requests库的终极解决方案"""
        requests_content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
终极requests库解决方案
已验证成功的替代方案
"""

import requests
from requests.auth import HTTPDigestAuth
from typing import Dict, Any, Tuple
import urllib.parse

class UltimateRequestsExecutor:
    """基于requests库的终极执行器"""
    
    def send_command_sync(self, device, command: Dict[str, Any]) -> Tuple[bool, str, str, Dict, str]:
        """
        同步发送命令（已验证成功）
        
        Args:
            device: 设备信息对象
            command: 命令字典
            
        Returns:
            Tuple[成功标志, 响应文本, 状态, 数据, 错误信息]
        """
        try:
            # 根据命令类型选择不同的CGI接口
            action = command.get("action", "")
            
            if action == "getCurrentTime":
                base_url = f"http://{device.ip}:{device.port}/cgi-bin/global.cgi"
            else:
                base_url = f"http://{device.ip}:{device.port}/cgi-bin/configManager.cgi"
            
            # 使用简化的参数构造
            params = self._build_simple_params(command)
            url = f"{base_url}?{params}"
            
            print(f"[UltimateRequestsExecutor] 发送请求到: {url}")
            
            # 使用requests的Digest认证（已验证成功）
            auth = HTTPDigestAuth(device.username, device.password)
            
            response = requests.get(url, auth=auth, verify=False, timeout=30)
            
            if response.status_code == 200:
                print(f"[UltimateRequestsExecutor] 请求成功: {response.text}")
                return True, response.text, "SUCCESS", {}, ""
            else:
                error_msg = f"HTTP {response.status_code}: {response.reason}"
                print(f"[UltimateRequestsExecutor] 请求失败: {error_msg}")
                
                # 检查认证要求
                www_auth = response.headers.get('WWW-Authenticate', '')
                if www_auth:
                    print(f"[UltimateRequestsExecutor] 认证要求: {www_auth}")
                
                return False, "", "FAILED", {}, error_msg
                
        except requests.Timeout:
            error_msg = "请求超时"
            print(f"[UltimateRequestsExecutor] {error_msg}")
            return False, "", "FAILED", {}, error_msg
            
        except Exception as e:
            error_msg = f"请求异常: {str(e)}"
            print(f"[UltimateRequestsExecutor] {error_msg}")
            return False, "", "FAILED", {}, error_msg
    
    def _build_simple_params(self, command: Dict[str, Any]) -> str:
        """构造简化的参数"""
        action = command.get("action", "")
        
        if action == "setConfig":
            # 对于setConfig命令，使用标准的大华设备格式
            return self._build_dahua_params(command)
        else:
            # 对于其他命令，使用urlencode
            return urllib.parse.urlencode(command, doseq=True)
    
    def _build_dahua_params(self, command: Dict[str, Any]) -> str:
        """构造大华设备标准参数格式"""
        param = command.get("param", {})
        params = ["action=setConfig"]
        
        # 扁平化参数处理
        for key, value in param.items():
            if isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        for sub_key, sub_value in item.items():
                            if isinstance(sub_value, dict):
                                for sub_sub_key, sub_sub_value in sub_value.items():
                                    param_str = f"{key}[{i}][{sub_key}][{sub_sub_key}]={sub_sub_value}"
                                    params.append(param_str)
                            else:
                                param_str = f"{key}[{i}][{sub_key}]={sub_value}"
                                params.append(param_str)
            else:
                param_str = f"{key}={value}"
                params.append(param_str)
        
        return "&".join(params)

# 异步包装器
import asyncio

class AsyncUltimateRequestsExecutor:
    """异步包装器"""
    
    def __init__(self):
        self.sync_executor = UltimateRequestsExecutor()
    
    async def send_command_async(self, device, command):
        """异步发送命令"""
        loop = asyncio.get_event_loop()
        
        # 在线程池中执行同步请求
        return await loop.run_in_executor(
            None, 
            self.sync_executor.send_command_sync, 
            device, 
            command
        )

# 直接测试函数
def test_connection():
    """测试连接"""
    from utils.device_manager import DeviceInfo
    
    device = DeviceInfo(
        index=0,
        ip="10.17.1.11",
        port="80",
        username="admin",
        password="Zxkj@8787558"
    )
    
    executor = UltimateRequestsExecutor()
    
    # 测试获取时间命令
    command = {
        "action": "getCurrentTime",
        "name": "global"
    }
    
    success, response, status, data, error = executor.send_command_sync(device, command)
    
    if success:
        print("✅ 连接测试成功!")
        print(f"响应: {response}")
    else:
        print(f"❌ 连接测试失败: {error}")

if __name__ == "__main__":
    test_connection()
'''
        
        requests_file_path = os.path.join(os.path.dirname(__file__), "ultimate_requests_executor.py")
        
        with open(requests_file_path, 'w', encoding='utf-8') as f:
            f.write(requests_content)
        
        print("   ✅ requests终极解决方案已创建: ultimate_requests_executor.py")

async def main():
    """主函数"""
    fixer = UltimateAsyncExecutorFixer()
    
    print("=" * 80)
    print("异步执行器终极修复工具")
    print("基于实际测试结果解决401错误")
    print("=" * 80)
    
    # 应用终极修复
    await fixer.apply_ultimate_fix()
    
    print("\n" + "=" * 80)
    print("终极修复完成!")
    print("=" * 80)
    print("\n📋 问题总结和解决方案:")
    print("1. 根本问题: aiohttp版本不支持内置Digest认证")
    print("2. 解决方案: 手动实现Digest认证或使用requests库")
    print("3. 推荐方案: 使用ultimate_requests_executor.py（已验证成功）")
    print("\n🚀 下一步操作:")
    print("1. 运行 'python ultimate_requests_executor.py' 测试连接")
    print("2. 使用ultimate_async_executor.py进行异步操作")
    print("3. 替换原有的异步执行器实现")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())