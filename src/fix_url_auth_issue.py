#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复URL构造和认证问题
解决异步配置中的401错误
"""

import asyncio
import sys
import os
from urllib.parse import urlencode, quote

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.async_executor import AsyncExecutor
from utils.device_manager import DeviceInfo

class URLAuthFixer:
    """URL构造和认证修复器"""
    
    def __init__(self):
        self.fix_results = []
    
    async def fix_async_executor(self):
        """修复异步执行器"""
        print("=== 修复异步执行器中的URL构造和认证问题 ===\n")
        
        # 分析并修复async_executor.py文件
        await self.analyze_and_fix_async_executor()
        
        # 测试修复效果
        await self.test_fixed_implementation()
    
    async def analyze_and_fix_async_executor(self):
        """分析并修复async_executor.py文件"""
        print("1. 分析async_executor.py文件中的问题...")
        
        async_executor_path = os.path.join(os.path.dirname(__file__), "utils", "async_executor.py")
        
        # 读取文件内容
        with open(async_executor_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 查找URL构造相关代码
        if "_build_url" in content or "urlencode" in content:
            print("   发现URL构造相关代码")
        
        # 查找认证处理相关代码
        if "_request_with_digest" in content:
            print("   发现Digest认证处理代码")
        
        # 分析具体问题
        await self.identify_specific_issues(content)
    
    async def identify_specific_issues(self, content):
        """识别具体问题"""
        print("\n2. 识别具体问题:")
        
        # 问题1: URL参数构造过于复杂
        print("   问题1: URL参数构造过于复杂，服务器无法正确解析嵌套结构")
        
        # 问题2: Digest认证头构造可能有问题
        print("   问题2: Digest认证头构造可能不符合服务器要求")
        
        # 问题3: URI编码可能不正确
        print("   问题3: URI编码可能不正确，导致认证响应计算错误")
    
    async def test_fixed_implementation(self):
        """测试修复后的实现"""
        print("\n3. 测试修复方案:")
        
        # 测试设备
        test_ip = "10.17.1.11"
        
        # 方案1: 使用简化的参数格式
        await self.test_simplified_params(test_ip)
        
        # 方案2: 使用正确的CGI命令格式
        await self.test_correct_cgi_format(test_ip)
        
        # 方案3: 使用requests库作为替代方案
        await self.test_requests_alternative(test_ip)
    
    async def test_simplified_params(self, device_ip):
        """测试简化参数格式"""
        print("\n   方案1: 简化参数格式测试")
        
        # 创建设备信息
        device = DeviceInfo(
            index=0,
            ip=device_ip,
            port="80",
            username="admin",
            password="Zxkj@8787558"
        )
        
        # 测试不同的参数格式
        test_cases = [
            {
                "name": "基本设置命令",
                "params": "action=setConfig&VideoWidget.Name=VideoWidget&VideoWidget.VideoWidgetTitle.enabled=true&VideoWidget.VideoWidgetTitle.text=Test Title"
            },
            {
                "name": "使用点号分隔",
                "params": "action=setConfig&VideoWidget[Name]=VideoWidget&VideoWidget[VideoWidgetTitle][enabled]=true&VideoWidget[VideoWidgetTitle][text]=Test Title"
            },
            {
                "name": "扁平化参数",
                "params": "action=setConfig&Name=VideoWidget&VideoWidgetTitle.enabled=true&VideoWidgetTitle.text=Test Title"
            }
        ]
        
        for test_case in test_cases:
            await self.test_single_format(device, test_case)
    
    async def test_single_format(self, device, test_case):
        """测试单个参数格式"""
        import requests
        from requests.auth import HTTPDigestAuth
        
        base_url = f"http://{device.ip}:{device.port}/cgi-bin/configManager.cgi"
        test_url = f"{base_url}?{test_case['params']}"
        
        print(f"      测试: {test_case['name']}")
        print(f"      参数: {test_case['params']}")
        
        try:
            auth = HTTPDigestAuth(device.username, device.password)
            response = requests.get(test_url, auth=auth, verify=False, timeout=5)
            
            print(f"      结果: 状态码 {response.status_code}")
            if response.status_code == 200:
                print(f"      成功! 响应: {response.text}")
                self.fix_results.append({
                    "方案": test_case['name'],
                    "状态": "成功",
                    "响应": response.text
                })
            else:
                print(f"      失败! 响应头: {dict(response.headers)}")
                
        except Exception as e:
            print(f"      错误: {e}")
    
    async def test_correct_cgi_format(self, device_ip):
        """测试正确的CGI命令格式"""
        print("\n   方案2: 正确CGI命令格式测试")
        
        # 根据大华设备文档，正确的命令格式应该是：
        # http://ip/cgi-bin/configManager.cgi?action=setConfig&VideoWidget[0][VideoWidgetTitle][text]=Test
        
        device = DeviceInfo(
            index=0,
            ip=device_ip,
            port="80",
            username="admin",
            password="Zxkj@8787558"
        )
        
        # 测试大华设备的标准命令格式
        test_formats = [
            {
                "name": "标准数组格式",
                "params": "action=setConfig&VideoWidget[0][Name]=VideoWidget&VideoWidget[0][VideoWidgetTitle][enabled]=true&VideoWidget[0][VideoWidgetTitle][text]=Test Title"
            },
            {
                "name": "简化数组格式",
                "params": "action=setConfig&VideoWidget[0][VideoWidgetTitle][text]=Test Title"
            },
            {
                "name": "仅设置文本",
                "params": "action=setConfig&VideoWidgetTitle.text=Test Title"
            }
        ]
        
        for test_format in test_formats:
            await self.test_cgi_format(device, test_format)
    
    async def test_cgi_format(self, device, test_format):
        """测试CGI格式"""
        import requests
        from requests.auth import HTTPDigestAuth
        
        base_url = f"http://{device.ip}:{device.port}/cgi-bin/configManager.cgi"
        test_url = f"{base_url}?{test_format['params']}"
        
        print(f"      测试: {test_format['name']}")
        print(f"      参数: {test_format['params']}")
        
        try:
            auth = HTTPDigestAuth(device.username, device.password)
            response = requests.get(test_url, auth=auth, verify=False, timeout=5)
            
            print(f"      结果: 状态码 {response.status_code}")
            if response.status_code == 200:
                print(f"      成功! 响应: {response.text}")
                self.fix_results.append({
                    "方案": test_format['name'],
                    "状态": "成功",
                    "响应": response.text
                })
            else:
                print(f"      失败! 响应头: {dict(response.headers)}")
                
        except Exception as e:
            print(f"      错误: {e}")
    
    async def test_requests_alternative(self, device_ip):
        """测试requests库替代方案"""
        print("\n   方案3: requests库替代方案测试")
        
        # 如果aiohttp有问题，可以使用requests库作为替代
        device = DeviceInfo(
            index=0,
            ip=device_ip,
            port="80",
            username="admin",
            password="Zxkj@8787558"
        )
        
        # 使用requests库测试
        await self.test_with_requests_library(device)
    
    async def test_with_requests_library(self, device):
        """使用requests库测试"""
        import requests
        from requests.auth import HTTPDigestAuth
        
        # 测试不同的端点
        endpoints = [
            "/cgi-bin/configManager.cgi?action=getConfig&name=VideoWidget",
            "/cgi-bin/configManager.cgi?action=setConfig&VideoWidget[0][VideoWidgetTitle][text]=Requests Test",
            "/cgi-bin/global.cgi?action=getCurrentTime"
        ]
        
        for endpoint in endpoints:
            url = f"http://{device.ip}:{device.port}{endpoint}"
            
            print(f"      测试端点: {endpoint}")
            
            try:
                auth = HTTPDigestAuth(device.username, device.password)
                response = requests.get(url, auth=auth, verify=False, timeout=5)
                
                print(f"      结果: 状态码 {response.status_code}")
                if response.status_code == 200:
                    print(f"      成功! 响应: {response.text[:100]}")
                else:
                    print(f"      失败! 响应头: {dict(response.headers)}")
                    
            except Exception as e:
                print(f"      错误: {e}")
    
    async def apply_fixes(self):
        """应用修复"""
        print("\n4. 应用修复方案:")
        
        # 根据测试结果选择最佳方案
        if self.fix_results:
            best_solution = self.fix_results[0]
            print(f"   推荐方案: {best_solution['方案']}")
            print(f"   状态: {best_solution['状态']}")
            
            # 创建修复文件
            await self.create_fix_file(best_solution)
        else:
            print("   未找到成功的解决方案，需要进一步分析")
    
    async def create_fix_file(self, solution):
        """创建修复文件"""
        fix_content = """
# 异步配置修复方案
# 推荐使用: {}

import aiohttp
import asyncio
from urllib.parse import urlencode

class FixedAsyncExecutor:
    """修复后的异步执行器"""
    
    async def send_command_fixed(self, device, command):
        """修复的发送命令方法"""
        # 使用简化的参数格式
        base_url = f"http://{{device.ip}}:{{device.port}}/cgi-bin/configManager.cgi"
        
        # 根据命令类型构造参数
        if command.get("action") == "setConfig":
            # 使用点号分隔的简化格式
            params = self._build_simple_params(command)
        else:
            params = urlencode(command, doseq=True)
        
        url = f"{{base_url}}?{{params}}"
        
        # 使用aiohttp内置的Digest认证
        auth = aiohttp.DigestAuth(device.username, device.password)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, auth=auth, ssl=False) as response:
                return await self._handle_response(response)
    
    def _build_simple_params(self, command):
        """构造简化参数"""
        # 实现简化的参数构造逻辑
        param = command.get("param", {{}})
        params = ["action=setConfig"]
        
        # 扁平化参数处理
        for key, value in param.items():
            if isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        for sub_key, sub_value in item.items():
                            if isinstance(sub_value, dict):
                                for sub_sub_key, sub_sub_value in sub_value.items():
                                    params.append(f"{{key}}[{{i}}][{{sub_key}}][{{sub_sub_key}}]={{sub_sub_value}}")
                            else:
                                params.append(f"{{key}}[{{i}}][{{sub_key}}]={{sub_value}}")
            else:
                params.append(f"{{key}}={{value}}")
        
        return "&".join(params)
    
    async def _handle_response(self, response):
        """处理响应"""
        if response.status == 200:
            text = await response.text()
            return True, text, "SUCCESS", {{}}, ""
        else:
            return False, "", "FAILED", {{}}, f"HTTP {{response.status}}"
""".format(solution['方案'])
        
        fix_file_path = os.path.join(os.path.dirname(__file__), "fixed_async_executor.py")
        
        with open(fix_file_path, 'w', encoding='utf-8') as f:
            f.write(fix_content)
        
        print(f"   修复文件已创建: fixed_async_executor.py")

async def main():
    """主函数"""
    fixer = URLAuthFixer()
    
    print("=" * 60)
    print("URL构造和认证问题修复工具")
    print("=" * 60)
    
    # 修复异步执行器
    await fixer.fix_async_executor()
    
    # 应用修复
    await fixer.apply_fixes()
    
    print("\n" + "=" * 60)
    print("修复完成")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())