#!/usr/bin/env python3
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
