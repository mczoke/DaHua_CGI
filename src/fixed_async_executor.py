#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复后的异步执行器
使用简化的URL构造和aiohttp内置认证
"""

import aiohttp
import asyncio
import json
from urllib.parse import urlencode
from typing import Dict, Any, Tuple

class FixedAsyncExecutor:
    """修复后的异步执行器"""
    
    async def send_command_fixed(self, device, command: Dict[str, Any]) -> Tuple[bool, str, str, Dict, str]:
        """
        修复的发送命令方法
        
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
            
            print(f"[FixedAsyncExecutor] 发送请求到: {url}")
            
            # 使用aiohttp内置的Digest认证
            auth = aiohttp.DigestAuth(device.username, device.password)
            
            timeout = aiohttp.ClientTimeout(total=30)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, auth=auth, ssl=False) as response:
                    
                    if response.status == 200:
                        text = await response.text()
                        print(f"[FixedAsyncExecutor] 请求成功: {text}")
                        return True, text, "SUCCESS", {}, ""
                    else:
                        error_msg = f"HTTP {response.status}: {response.reason}"
                        print(f"[FixedAsyncExecutor] 请求失败: {error_msg}")
                        
                        # 检查认证要求
                        www_auth = response.headers.get('WWW-Authenticate', '')
                        if www_auth:
                            print(f"[FixedAsyncExecutor] 认证要求: {www_auth}")
                        
                        return False, "", "FAILED", {}, error_msg
                        
        except asyncio.TimeoutError:
            error_msg = "请求超时"
            print(f"[FixedAsyncExecutor] {error_msg}")
            return False, "", "FAILED", {}, error_msg
            
        except Exception as e:
            error_msg = f"请求异常: {str(e)}"
            print(f"[FixedAsyncExecutor] {error_msg}")
            return False, "", "FAILED", {}, error_msg
    
    def _build_simple_params(self, command: Dict[str, Any]) -> str:
        """
        构造简化的参数
        
        根据命令类型使用不同的参数构造方式:
        - setConfig: 使用标准的大华设备格式
        - 其他命令: 使用urlencode
        """
        action = command.get("action", "")
        
        if action == "setConfig":
            # 对于setConfig命令，使用标准的大华设备格式
            return self._build_dahua_params(command)
        else:
            # 对于其他命令，使用urlencode
            return urlencode(command, doseq=True)
    
    def _build_dahua_params(self, command: Dict[str, Any]) -> str:
        """
        构造大华设备标准参数格式
        
        格式示例:
        action=setConfig&VideoWidget[0][VideoWidgetTitle][text]=Test Title
        """
        param = command.get("param", {})
        params = ["action=setConfig"]
        
        # 扁平化参数处理
        for key, value in param.items():
            if isinstance(value, list):
                # 处理数组格式
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        for sub_key, sub_value in item.items():
                            if isinstance(sub_value, dict):
                                # 嵌套字典处理
                                for sub_sub_key, sub_sub_value in sub_value.items():
                                    param_str = f"{key}[{i}][{sub_key}][{sub_sub_key}]={sub_sub_value}"
                                    params.append(param_str)
                            else:
                                # 简单值处理
                                param_str = f"{key}[{i}][{sub_key}]={sub_value}"
                                params.append(param_str)
            elif isinstance(value, dict):
                # 处理字典格式
                for sub_key, sub_value in value.items():
                    param_str = f"{key}.{sub_key}={sub_value}"
                    params.append(param_str)
            else:
                # 处理简单值
                param_str = f"{key}={value}"
                params.append(param_str)
        
        return "&".join(params)
    
    async def test_connection(self, device) -> bool:
        """
        测试设备连接
        
        Args:
            device: 设备信息对象
            
        Returns:
            连接是否成功
        """
        try:
            # 使用简单的获取时间命令测试连接
            test_command = {
                "action": "getCurrentTime",
                "name": "global"
            }
            
            base_url = f"http://{device.ip}:{device.port}/cgi-bin/global.cgi"
            params = urlencode(test_command, doseq=True)
            url = f"{base_url}?{params}"
            
            auth = aiohttp.DigestAuth(device.username, device.password)
            timeout = aiohttp.ClientTimeout(total=10)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, auth=auth, ssl=False) as response:
                    return response.status == 200
                    
        except Exception:
            return False

# 兼容性包装器
class AsyncExecutor:
    """兼容性包装器，保持原有接口"""
    
    def __init__(self):
        self.fixed_executor = FixedAsyncExecutor()
    
    async def send_command_async(self, device, command):
        """保持原有接口"""
        return await self.fixed_executor.send_command_fixed(device, command)
