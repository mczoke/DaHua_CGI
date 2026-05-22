"""
修复后的异步执行器 - 基于requests库的解决方案
- 使用requests + asyncio线程池，解决aiohttp的Digest认证问题
- 已验证成功的替代方案，避免401认证错误
"""

import asyncio
import threading
import urllib.parse
from typing import Dict, Any, Tuple
import requests
from requests.auth import HTTPDigestAuth

# 导入日志管理器以记录详细元数据
from utils.log_manager import LogManager

class SyncRequestsExecutor:
    """同步requests执行器"""
    
    def send_command_sync(self, device, command) -> Tuple[bool, str, str, Dict, str]:
        """
        同步发送命令（已验证成功）
        
        Args:
            device: 设备信息对象
            command: 命令字典或字符串
            
        Returns:
            Tuple[成功标志, 响应文本, 状态, 数据, 错误信息]
        """
        try:
            # 处理字符串命令：转换为字典格式
            if isinstance(command, str):
                # 解析字符串命令格式："VideoWidget[0].CustomTitle[1].EncodeBlend=true"
                if '=' in command:
                    key, value = command.split('=', 1)
                    command = {
                        "action": "setConfig",
                        "param": {
                            key: value
                        }
                    }
                else:
                    # 如果不是setConfig命令，使用默认格式
                    command = {
                        "action": command
                    }
            
            # 根据命令类型选择不同的CGI接口
            action = command.get("action", "")
            
            if action == "getCurrentTime":
                base_url = f"http://{device.ip}:{device.port}/cgi-bin/global.cgi"
            else:
                base_url = f"http://{device.ip}:{device.port}/cgi-bin/configManager.cgi"
            
            # 使用简化的参数构造
            params = self._build_simple_params(command)
            url = f"{base_url}?{params}"
            
            print(f"[FixedAsyncExecutor] 发送请求到: {url}")
            
            # 使用requests的Digest认证（已验证成功）
            auth = HTTPDigestAuth(device.username, device.password)
            
            response = requests.get(url, auth=auth, verify=False, timeout=30)
            
            if response.status_code == 200:
                print(f"[FixedAsyncExecutor] 请求成功: {response.text}")
                return True, response.text, "SUCCESS", dict(response.headers), ""
            else:
                error_msg = f"HTTP {response.status_code}: {response.reason}"
                print(f"[FixedAsyncExecutor] 请求失败: {error_msg}")
                
                # 检查认证要求
                www_auth = response.headers.get('WWW-Authenticate', '')
                if www_auth:
                    print(f"[FixedAsyncExecutor] 认证要求: {www_auth}")
                
                return False, "", "FAILED", dict(response.headers), error_msg
                
        except requests.Timeout:
            error_msg = "请求超时"
            print(f"[FixedAsyncExecutor] {error_msg}")
            return False, "", "FAILED", {}, error_msg
            
        except Exception as e:
            error_msg = f"请求异常: {str(e)}"
            print(f"[FixedAsyncExecutor] {error_msg}")
            return False, "", "FAILED", {}, error_msg
    
    def _build_simple_params(self, command: Dict[str, Any]) -> str:
        """构造简化的参数"""
        action = command.get("action", "")
        
        if action == "setConfig":
            # 对于setConfig命令，检查param字段的结构
            param = command.get("param", {})
            
            # 如果param是简单的键值对（如{"VideoWidget[0].CustomTitle[1].EncodeBlend": "true"}），
            # 则直接使用urlencode而不是复杂的_dahua_params
            if param and isinstance(param, dict) and len(param) == 1:
                first_key = list(param.keys())[0]
                first_value = param[first_key]
                
                # 检查是否是简单的键值对格式（如包含[0]索引的复杂键名）
                if isinstance(first_value, str) and '[' in first_key:
                    # 对于这种格式，直接构造参数：action=setConfig&VideoWidget[0].CustomTitle[1].EncodeBlend=true
                    return f"action=setConfig&{first_key}={first_value}"
                else:
                    # 对于复杂结构，使用_dahua_params
                    return self._build_dahua_params(command)
            else:
                # 对于复杂结构，使用_dahua_params
                return self._build_dahua_params(command)
        elif action == "getCurrentTime":
            # 对于getCurrentTime命令，使用简单的action参数
            return "action=getCurrentTime"
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
                        # 处理简单值列表
                        param_str = f"{key}[{i}]={item}"
                        params.append(param_str)
            elif isinstance(value, dict):
                # 处理嵌套字典
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, dict):
                        for sub_sub_key, sub_sub_value in sub_value.items():
                            param_str = f"{key}[{sub_key}][{sub_sub_key}]={sub_sub_value}"
                            params.append(param_str)
                    else:
                        param_str = f"{key}[{sub_key}]={sub_value}"
                        params.append(param_str)
            else:
                # 处理简单键值对
                param_str = f"{key}={value}"
                params.append(param_str)
        
        return "&".join(params)


class AsyncExecutor:
    """修复后的异步执行器，使用requests + asyncio线程池"""

    def __init__(self, timeout=30, verify_ssl=False, max_connections=100, auth_method='digest'):
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.max_connections = max_connections
        self.auth_method = auth_method
        self.sync_executor = SyncRequestsExecutor()
        self._closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def close(self):
        self._closed = True

    async def send_command_async(self, device, command):
        """
        异步发送命令，使用线程池执行同步requests请求
        
        Args:
            device: 设备信息对象
            command: 命令字典
            
        Returns:
            Tuple[成功标志, 响应文本, 状态, 数据, 错误信息]
        """
        # 安全获取事件循环：如果当前线程没有事件循环，则创建新的事件循环
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # 当前线程没有事件循环，创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # 在线程池中执行同步请求
        return await loop.run_in_executor(
            None, 
            self.sync_executor.send_command_sync, 
            device, 
            command
        )


class AsyncIOManager:
    """基于requests库的异步管理器，提供与原有接口兼容的异步执行功能"""

    def __init__(self, timeout=30, verify_ssl=False, max_connections=100, auth_method='digest'):
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.max_connections = max_connections
        self.auth_method = auth_method
        self.sync_executor = SyncRequestsExecutor()
        self._closed = False

    def run_coroutine(self, coro):
        """运行协程（兼容原有接口）"""
        import asyncio
        return asyncio.run(coro)

    def send_command(self, device, command):
        """兼容同步调用：提交异步发送并返回 Future（已弃用，请使用send_command_async）"""
        import asyncio
        import concurrent.futures
        
        async def async_send():
            return await self.send_command_async(device, command)
        
        # 返回concurrent.futures.Future对象，调用者需要正确处理Future
        future = asyncio.run_coroutine_threadsafe(async_send(), asyncio.get_event_loop())
        
        # 立即等待Future完成，避免协程未被等待的警告
        try:
            return future.result(timeout=self.timeout)
        except concurrent.futures.TimeoutError:
            return False, "请求超时", "TIMEOUT", {}, ""
        except Exception as e:
            return False, f"异步请求异常: {e}", "EXCEPTION", {}, str(e)[:200]

    async def send_command_async(self, device, command, use_url_auth=False):
        """异步发送命令，使用线程池执行同步requests请求"""
        import asyncio
        
        # 安全获取事件循环：如果当前线程没有事件循环，则创建新的事件循环
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # 当前线程没有事件循环，创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # 在线程池中执行同步请求
        result = await loop.run_in_executor(
            None, 
            self.sync_executor.send_command_sync, 
            device, 
            command
        )
        
        # 转换返回格式以兼容原有接口
        ok, text, status, headers, error = result
        return (ok, text, status, headers, error)

    def close(self, wait=True):
        """关闭管理器"""
        self._closed = True


# 示例：如何并发发送多条命令
async def send_multiple_commands(device, commands, timeout=10):
    async with AsyncExecutor(timeout=timeout) as ex:
        results = []
        for cmd in commands:
            ok, msg, status, headers, error = await ex.send_command_async(device, cmd)
            results.append((ok, msg))
        return results