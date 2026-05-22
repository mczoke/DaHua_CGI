#!/usr/bin/env python3
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
