#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最终修复异步执行器 - 解决401错误
基于调试结果，修复URL构造和认证问题
"""

import asyncio
import sys
import os
import json
from urllib.parse import urlencode

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.device_manager import DeviceInfo

class AsyncExecutorFixer:
    """异步执行器修复器"""
    
    def __init__(self):
        self.fix_applied = False
    
    async def apply_final_fix(self):
        """应用最终修复"""
        print("=== 应用最终修复方案 ===\n")
        
        # 1. 分析当前问题
        await self.analyze_current_issues()
        
        # 2. 创建修复后的异步执行器
        await self.create_fixed_async_executor()
        
        # 3. 测试修复效果
        await self.test_fixed_solution()
        
        # 4. 提供替代方案
        await self.provide_alternative_solutions()
    
    async def analyze_current_issues(self):
        """分析当前问题"""
        print("1. 分析当前异步执行器的问题:")
        
        async_executor_path = os.path.join(os.path.dirname(__file__), "utils", "async_executor.py")
        
        try:
            with open(async_executor_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 检查问题
            issues_found = []
            
            if "_request_with_digest" in content:
                issues_found.append("使用自定义Digest认证实现而不是aiohttp内置认证")
            
            if "_parse_www_authenticate" in content:
                issues_found.append("自定义认证头解析可能存在正则表达式问题")
            
            if "_build_digest_auth_header" in content:
                issues_found.append("自定义认证头构造可能存在URI计算问题")
            
            # 检查URL构造
            if "urlencode" in content and "param" in content:
                issues_found.append("URL参数构造过于复杂，使用嵌套JSON结构")
            
            print("   发现的问题:")
            for i, issue in enumerate(issues_found, 1):
                print(f"   {i}. {issue}")
                
        except Exception as e:
            print(f"   错误: {e}")
    
    async def create_fixed_async_executor(self):
        """创建修复后的异步执行器"""
        print("\n2. 创建修复后的异步执行器:")
        
        fixed_content = '''#!/usr/bin/env python3
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
'''
        
        fixed_file_path = os.path.join(os.path.dirname(__file__), "fixed_async_executor.py")
        
        with open(fixed_file_path, 'w', encoding='utf-8') as f:
            f.write(fixed_content)
        
        print("   ✅ 修复后的异步执行器已创建: fixed_async_executor.py")
        self.fix_applied = True
    
    async def test_fixed_solution(self):
        """测试修复效果"""
        print("\n3. 测试修复效果:")
        
        if not self.fix_applied:
            print("   ❌ 修复未应用，跳过测试")
            return
        
        # 导入修复后的执行器
        sys.path.insert(0, os.path.dirname(__file__))
        
        try:
            from fixed_async_executor import FixedAsyncExecutor
            
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
                    "name": "设置视频部件标题",
                    "command": {
                        "action": "setConfig",
                        "param": {
                            "VideoWidget": [
                                {
                                    "Name": "VideoWidget",
                                    "VideoWidgetTitle": {
                                        "enabled": True,
                                        "text": "Fixed Test Title"
                                    }
                                }
                            ]
                        }
                    }
                },
                {
                    "name": "获取配置",
                    "command": {
                        "action": "getConfig",
                        "name": "VideoWidget"
                    }
                }
            ]
            
            executor = FixedAsyncExecutor()
            
            for test in test_commands:
                print(f"\n   测试: {test['name']}")
                
                success, response, status, data, error = await executor.send_command_fixed(device, test['command'])
                
                if success:
                    print(f"   ✅ 成功! 状态: {status}")
                    print(f"   响应: {response}")
                else:
                    print(f"   ❌ 失败! 错误: {error}")
                    
        except Exception as e:
            print(f"   ❌ 测试错误: {e}")
    
    async def provide_alternative_solutions(self):
        """提供替代方案"""
        print("\n4. 替代解决方案:")
        
        # 方案1: 使用requests库
        await self.create_requests_solution()
        
        # 方案2: 简化参数构造器
        await self.create_simple_param_builder()
    
    async def create_requests_solution(self):
        """创建requests库解决方案"""
        requests_content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用requests库的替代方案
避免aiohttp的认证问题
"""

import requests
from requests.auth import HTTPDigestAuth
from typing import Dict, Any, Tuple

class RequestsAsyncExecutor:
    """基于requests库的异步执行器"""
    
    def send_command_sync(self, device, command: Dict[str, Any]) -> Tuple[bool, str, str, Dict, str]:
        """
        同步发送命令（可用于异步环境中的线程池）
        
        Args:
            device: 设备信息对象
            command: 命令字典
            
        Returns:
            Tuple[成功标志, 响应文本, 状态, 数据, 错误信息]
        """
        try:
            # 构造URL
            base_url = f"http://{device.ip}:{device.port}/cgi-bin/configManager.cgi"
            
            # 使用简化的参数构造
            params = self._build_simple_params(command)
            url = f"{base_url}?{params}"
            
            print(f"[RequestsExecutor] 发送请求到: {url}")
            
            # 使用requests的Digest认证
            auth = HTTPDigestAuth(device.username, device.password)
            
            response = requests.get(url, auth=auth, verify=False, timeout=30)
            
            if response.status_code == 200:
                print(f"[RequestsExecutor] 请求成功: {response.text}")
                return True, response.text, "SUCCESS", {}, ""
            else:
                error_msg = f"HTTP {response.status_code}: {response.reason}"
                print(f"[RequestsExecutor] 请求失败: {error_msg}")
                return False, "", "FAILED", {}, error_msg
                
        except requests.Timeout:
            error_msg = "请求超时"
            print(f"[RequestsExecutor] {error_msg}")
            return False, "", "FAILED", {}, error_msg
            
        except Exception as e:
            error_msg = f"请求异常: {str(e)}"
            print(f"[RequestsExecutor] {error_msg}")
            return False, "", "FAILED", {}, error_msg
    
    def _build_simple_params(self, command: Dict[str, Any]) -> str:
        """构造简化的参数"""
        import urllib.parse
        
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

# 在异步环境中使用
import asyncio

class AsyncRequestsExecutor:
    """异步包装器"""
    
    def __init__(self):
        self.sync_executor = RequestsAsyncExecutor()
    
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
'''
        
        requests_file_path = os.path.join(os.path.dirname(__file__), "requests_async_executor.py")
        
        with open(requests_file_path, 'w', encoding='utf-8') as f:
            f.write(requests_content)
        
        print("   ✅ requests替代方案已创建: requests_async_executor.py")
    
    async def create_simple_param_builder(self):
        """创建简化参数构造器"""
        builder_content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化参数构造器
将复杂JSON参数转换为标准CGI格式
"""

class SimpleParamBuilder:
    """简化参数构造器"""
    
    @staticmethod
    def build_dahua_params(command: dict) -> str:
        """
        将复杂命令转换为大华设备标准参数格式
        
        Args:
            command: 原始命令字典
            
        Returns:
            标准CGI参数字符串
        """
        action = command.get("action", "")
        
        if action != "setConfig":
            # 非setConfig命令直接返回
            import urllib.parse
            return urllib.parse.urlencode(command, doseq=True)
        
        param = command.get("param", {})
        params = ["action=setConfig"]
        
        # 递归处理参数
        SimpleParamBuilder._process_params(param, "", params)
        
        return "&".join(params)
    
    @staticmethod
    def _process_params(data, prefix, params):
        """递归处理参数"""
        if isinstance(data, dict):
            for key, value in data.items():
                new_prefix = f"{prefix}[{key}]" if prefix else key
                SimpleParamBuilder._process_params(value, new_prefix, params)
        elif isinstance(data, list):
            for i, item in enumerate(data):
                new_prefix = f"{prefix}[{i}]" if prefix else str(i)
                SimpleParamBuilder._process_params(item, new_prefix, params)
        else:
            # 基本类型
            param_str = f"{prefix}={data}"
            params.append(param_str)

# 使用示例
if __name__ == "__main__":
    builder = SimpleParamBuilder()
    
    # 复杂命令示例
    complex_command = {
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
    
    simple_params = builder.build_dahua_params(complex_command)
    print("简化后的参数:")
    print(simple_params)
    
    # 输出: action=setConfig&VideoWidget[0][Name]=VideoWidget&VideoWidget[0][VideoWidgetTitle][enabled]=True&VideoWidget[0][VideoWidgetTitle][text]=Test Title
'''
        
        builder_file_path = os.path.join(os.path.dirname(__file__), "simple_param_builder.py")
        
        with open(builder_file_path, 'w', encoding='utf-8') as f:
            f.write(builder_content)
        
        print("   ✅ 简化参数构造器已创建: simple_param_builder.py")

async def main():
    """主函数"""
    fixer = AsyncExecutorFixer()
    
    print("=" * 80)
    print("异步执行器最终修复工具")
    print("解决401认证错误问题")
    print("=" * 80)
    
    # 应用最终修复
    await fixer.apply_final_fix()
    
    print("\n" + "=" * 80)
    print("修复完成!")
    print("=" * 80)
    print("\n下一步操作:")
    print("1. 使用 fixed_async_executor.py 替换原有的异步执行器")
    print("2. 或者使用 requests_async_executor.py 作为替代方案")
    print("3. 使用 simple_param_builder.py 简化参数构造")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())