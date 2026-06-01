"""
修复后的异步执行器 - 基于requests库的解决方案
- 使用requests + asyncio线程池，解决aiohttp的Digest认证问题
- 已验证成功的替代方案，避免401认证错误

v2.0 (2026-06-01):
  - SyncRequestsExecutor: 添加重试机制 (Retry total=3, backoff_factor=0.5)
  - AsyncExecutor/AsyncIOManager: 添加固定 ThreadPoolExecutor(max_workers=50)
  - verify_ssl 默认改为 True, 通过配置控制
  - close() 优雅关闭线程池
"""

import asyncio
import concurrent.futures
import logging
import threading
import urllib.parse
from typing import Dict, Any, Tuple, Optional

import requests
from requests.adapters import HTTPAdapter
from requests.auth import HTTPDigestAuth
from urllib3.util.retry import Retry

from utils.log_manager import LogManager

logger = logging.getLogger(__name__)


class SyncRequestsExecutor:
    """同步requests执行器（带重试机制）"""

    def __init__(self, verify_ssl: bool = True, request_timeout: int = 30):
        self.verify_ssl = verify_ssl
        self.request_timeout = request_timeout
        self._session: Optional[requests.Session] = None

    def _get_session(self) -> requests.Session:
        """获取带重试配置的 requests Session（惰性创建）"""
        if self._session is None:
            self._session = requests.Session()
            retry_strategy = Retry(
                total=3,
                backoff_factor=0.5,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["GET", "POST"],
            )
            adapter = HTTPAdapter(
                pool_connections=100,
                pool_maxsize=100,
                max_retries=retry_strategy,
            )
            self._session.mount("http://", adapter)
            self._session.mount("https://", adapter)
        return self._session

    def send_command_sync(
        self, device, command
    ) -> Tuple[bool, str, str, Dict, str]:
        """
        同步发送命令（带自动重试）

        Args:
            device: 设备信息对象
            command: 命令字典或字符串

        Returns:
            Tuple[成功标志, 响应文本, 状态, 数据, 错误信息]
        """
        session = self._get_session()

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

            logger.info(f"发送请求到: {url}")

            # 使用requests的Digest认证
            auth = HTTPDigestAuth(device.username, device.password)

            response = session.get(
                url,
                auth=auth,
                verify=self.verify_ssl,
                timeout=self.request_timeout,
            )

            if response.status_code == 200:
                logger.info(f"请求成功: {response.text[:500]}")
                return True, response.text, "SUCCESS", dict(response.headers), ""
            else:
                error_msg = f"HTTP {response.status_code}: {response.reason}"
                logger.warning(f"请求失败: {error_msg}")

                # 检查认证要求
                www_auth = response.headers.get('WWW-Authenticate', '')
                if www_auth:
                    logger.warning(f"认证要求: {www_auth}")

                return False, "", "FAILED", dict(response.headers), error_msg

        except requests.Timeout:
            error_msg = "请求超时"
            logger.error(error_msg)
            return False, "", "FAILED", {}, error_msg

        except Exception as e:
            error_msg = f"请求异常: {str(e)}"
            logger.error(error_msg)
            return False, "", "FAILED", {}, error_msg

    def close(self) -> None:
        """关闭底层的 requests Session"""
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None

    def _build_simple_params(self, command: Dict[str, Any]) -> str:
        """构造简化的参数"""
        action = command.get("action", "")

        if action == "setConfig":
            # 对于setConfig命令，检查param字段的结构
            param = command.get("param", {})

            # 如果param是简单的键值对，直接构造
            if param and isinstance(param, dict) and len(param) == 1:
                first_key = list(param.keys())[0]
                first_value = param[first_key]

                # 检查是否是简单的键值对格式
                if isinstance(first_value, str) and '[' in first_key:
                    return f"action=setConfig&{first_key}={first_value}"
                else:
                    return self._build_dahua_params(command)
            else:
                return self._build_dahua_params(command)
        elif action == "getCurrentTime":
            return "action=getCurrentTime"
        else:
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
                        param_str = f"{key}[{i}]={item}"
                        params.append(param_str)
            elif isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, dict):
                        for sub_sub_key, sub_sub_value in sub_value.items():
                            param_str = f"{key}[{sub_key}][{sub_sub_key}]={sub_sub_value}"
                            params.append(param_str)
                    else:
                        param_str = f"{key}[{sub_key}]={sub_value}"
                        params.append(param_str)
            else:
                param_str = f"{key}={value}"
                params.append(param_str)

        return "&".join(params)


class AsyncExecutor:
    """
    异步执行器，使用 requests + asyncio 线程池
    内部维护 ThreadPoolExecutor(max_workers=50) 用于并发执行同步请求
    """

    def __init__(
        self,
        timeout: int = 30,
        verify_ssl: bool = True,
        max_connections: int = 100,
        auth_method: str = 'digest',
    ):
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.max_connections = max_connections
        self.auth_method = auth_method
        self.sync_executor = SyncRequestsExecutor(
            verify_ssl=verify_ssl,
            request_timeout=timeout,
        )
        self._thread_pool: Optional[concurrent.futures.ThreadPoolExecutor] = None
        self._closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    def _get_thread_pool(self) -> concurrent.futures.ThreadPoolExecutor:
        """惰性创建固定线程池"""
        if self._thread_pool is None:
            self._thread_pool = concurrent.futures.ThreadPoolExecutor(
                max_workers=50,
                thread_name_prefix="async_executor",
            )
        return self._thread_pool

    async def close(self) -> None:
        """优雅关闭：关闭线程池和 sync_executor"""
        self._closed = True
        if self._thread_pool is not None:
            self._thread_pool.shutdown(wait=True)
            self._thread_pool = None
        self.sync_executor.close()

    async def send_command_async(self, device, command):
        """
        异步发送命令，使用线程池执行同步requests请求

        Args:
            device: 设备信息对象
            command: 命令字典

        Returns:
            Tuple[成功标志, 响应文本, 状态, 数据, 错误信息]
        """
        pool = self._get_thread_pool()

        # 在线程池中执行同步请求
        return await asyncio.get_event_loop().run_in_executor(
            pool,
            self.sync_executor.send_command_sync,
            device,
            command,
        )


class AsyncIOManager:
    """
    基于requests库的异步管理器，提供与原有接口兼容的异步执行功能
    内部维护 ThreadPoolExecutor(max_workers=50) 用于并发执行同步请求
    """

    def __init__(
        self,
        timeout: int = 30,
        verify_ssl: bool = True,
        max_connections: int = 100,
        auth_method: str = 'digest',
    ):
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.max_connections = max_connections
        self.auth_method = auth_method
        self.sync_executor = SyncRequestsExecutor(
            verify_ssl=verify_ssl,
            request_timeout=timeout,
        )
        self._thread_pool: Optional[concurrent.futures.ThreadPoolExecutor] = None
        self._closed = False

    def _get_thread_pool(self) -> concurrent.futures.ThreadPoolExecutor:
        """惰性创建固定线程池"""
        if self._thread_pool is None:
            self._thread_pool = concurrent.futures.ThreadPoolExecutor(
                max_workers=50,
                thread_name_prefix="async_io_manager",
            )
        return self._thread_pool

    def run_coroutine(self, coro):
        """运行协程（兼容原有接口）"""
        return asyncio.run(coro)

    def send_command(self, device, command):
        """
        兼容同步调用：提交异步发送并返回结果
        注意：此方法会阻塞等待结果，保持与原有接口兼容
        """
        import asyncio
        import concurrent.futures as cf

        async def async_send():
            return await self.send_command_async(device, command)

        try:
            # 检查当前事件循环状态
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果事件循环正在运行，使用线程池执行
                pool = self._get_thread_pool()
                future = pool.submit(asyncio.run, async_send())
                return future.result(timeout=self.timeout)
        except RuntimeError:
            pass

        # 默认：直接运行协程
        return asyncio.run(async_send())

    async def send_command_async(
        self, device, command, use_url_auth: bool = False
    ):
        """
        异步发送命令，使用线程池执行同步requests请求

        Args:
            device: 设备信息对象
            command: 命令字符串或字典
            use_url_auth: 是否使用URL内嵌认证（旧兼容模式）

        Returns:
            Tuple[成功标志, 响应文本, 状态, 数据, 错误信息]
        """
        pool = self._get_thread_pool()

        # 在线程池中执行同步请求
        result = await asyncio.get_event_loop().run_in_executor(
            pool,
            self.sync_executor.send_command_sync,
            device,
            command,
        )

        # 转换返回格式以兼容原有接口
        ok, text, status, headers, error = result
        return (ok, text, status, headers, error)

    def close(self, wait: bool = True) -> None:
        """关闭管理器：优雅关闭线程池和 sync_executor"""
        self._closed = True
        if self._thread_pool is not None:
            self._thread_pool.shutdown(wait=wait)
            self._thread_pool = None
        self.sync_executor.close()


# 示例：如何并发发送多条命令
async def send_multiple_commands(device, commands, timeout=10):
    async with AsyncExecutor(timeout=timeout) as ex:
        results = []
        for cmd in commands:
            ok, msg, status, headers, error = await ex.send_command_async(device, cmd)
            results.append((ok, msg))
        return results
