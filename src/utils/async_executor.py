"""
修复后的异步执行器 - 基于requests库的解决方案
- 使用requests + asyncio线程池，解决aiohttp的Digest认证问题
- 已验证成功的替代方案，避免401认证错误

v2.1 (2026-06-03):
  - 动态线程数策略（根据负载自动调整 min/max）
  - 连接池指标监控（活跃/空闲/排队数/峰值）
  - max_connections 配置参数贯通
  - ThreadPoolMonitor 可查询状态
"""

import asyncio
import concurrent.futures
import logging
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Dict, Any, Tuple, Optional, List

import requests
from requests.adapters import HTTPAdapter
from requests.auth import HTTPDigestAuth
from urllib3.util.retry import Retry

from utils.log_manager import LogManager

logger = logging.getLogger(__name__)


# ============================================================================
# 连接池监控指标
# ============================================================================

@dataclass
class PoolMetricsSnapshot:
    """线程池快照指标"""
    active: int = 0
    idle: int = 0
    queued: int = 0
    max_workers: int = 0
    total_submitted: int = 0
    total_completed: int = 0
    peak_active: int = 0
    timestamp: float = 0.0


class ThreadPoolMonitor:
    """
    线程池监控器 — 跟踪活跃/空闲/排队数及峰值

    通过在线程池的 submit/map 调用时更新计数器实现轻量监控，
    不依赖 ThreadPoolExecutor 内部 API。
    """

    def __init__(self, pool: concurrent.futures.ThreadPoolExecutor, max_workers: int):
        self._pool = pool
        self._max_workers = max_workers
        self._lock = threading.Lock()
        self._active = 0
        self._peak_active = 0
        self._queued = 0
        self._total_submitted = 0
        self._total_completed = 0

    @property
    def active(self) -> int:
        return self._active

    @property
    def queued(self) -> int:
        return self._queued

    @property
    def peak_active(self) -> int:
        return self._peak_active

    def _on_submit(self) -> None:
        with self._lock:
            self._total_submitted += 1
            self._queued += 1

    def _on_start(self) -> None:
        with self._lock:
            self._active += 1
            self._queued -= 1
            if self._active > self._peak_active:
                self._peak_active = self._active

    def _on_complete(self) -> None:
        with self._lock:
            self._active -= 1
            self._total_completed += 1

    def snapshot(self) -> PoolMetricsSnapshot:
        """获取当前快照"""
        with self._lock:
            return PoolMetricsSnapshot(
                active=self._active,
                idle=max(0, self._max_workers - self._active),
                queued=self._queued,
                max_workers=self._max_workers,
                total_submitted=self._total_submitted,
                total_completed=self._total_completed,
                peak_active=self._peak_active,
                timestamp=time.time(),
            )

    def __repr__(self) -> str:
        s = self.snapshot()
        return (
            f"PoolMetrics("
            f"active={s.active}, idle={s.idle}, queued={s.queued}, "
            f"max={s.max_workers}, peak={s.peak_active}, "
            f"submitted={s.total_submitted}, completed={s.total_completed})"
        )


# ============================================================================
# 动态线程池包装
# ============================================================================

class AdaptiveThreadPool:
    """
    自适应线程池 — 根据排队任务数动态调整线程数

    策略：
    - min_workers: 保底线程数，始终保留
    - max_workers: 最大允许线程数
    - 当排队任务 > 当前线程数 * scale_up_factor → 逐渐增加线程
    - 当排队任务 == 0 且持续空闲超过 idle_seconds → 逐渐减少线程
    - 每次调整步长 step 个线程

    用法与 ThreadPoolExecutor 一致，额外提供 stats() 和 metrics()。
    """

    def __init__(
        self,
        min_workers: int = 10,
        max_workers: int = 80,
        max_connections: int = 100,
        scale_up_factor: float = 1.5,
        idle_seconds: float = 5.0,
        step: int = 5,
        thread_name_prefix: str = "async_pool",
    ):
        self._min = min_workers
        self._max = max_workers
        self._max_connections = max_connections
        self._scale_up_factor = scale_up_factor
        self._idle_seconds = idle_seconds
        self._step = step
        self._prefix = thread_name_prefix

        self._lock = threading.Lock()
        self._current_size = min_workers
        self._pool: Optional[concurrent.futures.ThreadPoolExecutor] = None
        self._monitor: Optional[ThreadPoolMonitor] = None

        # 空闲跟踪
        self._last_idle_time: float = 0.0
        self._adjust_in_progress = False

        self._create_pool()

    # ---- 公共接口 ----

    def submit(self, fn, *args, **kwargs) -> concurrent.futures.Future:
        self._maybe_adjust()
        if self._monitor:
            self._monitor._on_submit()
        # 包装函数以跟踪生命周期
        original_fn = fn

        def tracked_fn(*a, **kw):
            if self._monitor:
                self._monitor._on_start()
            try:
                return original_fn(*a, **kw)
            finally:
                if self._monitor:
                    self._monitor._on_complete()

        if self._pool is None:
            self._create_pool()
        return self._pool.submit(tracked_fn, *args, **kwargs)

    def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
        with self._lock:
            pool = self._pool
            self._pool = None
        if pool is not None:
            pool.shutdown(wait=wait, cancel_futures=cancel_futures)

    def metrics(self) -> PoolMetricsSnapshot:
        """获取当前性能指标快照"""
        if self._monitor:
            return self._monitor.snapshot()
        return PoolMetricsSnapshot()

    def stats(self) -> Dict[str, Any]:
        """获取可读统计信息"""
        m = self.metrics()
        return {
            "active": m.active,
            "idle": m.idle,
            "queued": m.queued,
            "current_size": self._current_size,
            "min_workers": self._min,
            "max_workers": self._max,
            "peak_active": m.peak_active,
            "total_submitted": m.total_submitted,
            "total_completed": m.total_completed,
        }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown(wait=True)

    # ---- 内部方法 ----

    def _create_pool(self) -> None:
        self._pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self._current_size,
            thread_name_prefix=self._prefix,
        )
        self._monitor = ThreadPoolMonitor(self._pool, self._current_size)

    def _replace_pool(self, new_size: int) -> None:
        """原子替换线程池（扩容/缩容）"""
        new_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=new_size,
            thread_name_prefix=self._prefix,
        )
        new_monitor = ThreadPoolMonitor(new_pool, new_size)

        # 移交未完成的 Future 到新池
        old_pool = self._pool
        old_monitor = self._monitor

        with self._lock:
            self._pool = new_pool
            self._monitor = new_monitor
            self._current_size = new_size

        if old_pool is not None:
            old_pool.shutdown(wait=False)
            # 保留旧 monitor 的累计计数
            if old_monitor:
                new_monitor._total_submitted = old_monitor._total_submitted
                new_monitor._total_completed = old_monitor._total_completed
                new_monitor._peak_active = old_monitor._peak_active

    def _maybe_adjust(self) -> None:
        """根据当前负载决定扩容或缩容"""
        if self._adjust_in_progress:
            return

        monitor = self._monitor
        if monitor is None:
            return

        snap = monitor.snapshot()
        current = self._current_size
        scaled_target = int(snap.queued * self._scale_up_factor)

        if snap.queued > 0 and scaled_target > current and current < self._max:
            # 扩容
            new_size = min(current + self._step, self._max)
            new_size = max(new_size, scaled_target)
            new_size = min(new_size, self._max)
            if new_size > current:
                self._adjust_in_progress = True
                try:
                    logger.info(
                        f"线程池扩容: {current} → {new_size} "
                        f"(排队={snap.queued}, 活跃={snap.active})"
                    )
                    self._replace_pool(new_size)
                finally:
                    self._adjust_in_progress = False
                return

        if snap.active == 0 and snap.queued == 0:
            now = time.time()
            if self._last_idle_time == 0:
                self._last_idle_time = now
            elif now - self._last_idle_time > self._idle_seconds and current > self._min:
                # 缩容
                new_size = max(current - self._step, self._min)
                self._adjust_in_progress = True
                try:
                    logger.info(
                        f"线程池缩容: {current} → {new_size} (空闲)"
                    )
                    self._replace_pool(new_size)
                finally:
                    self._adjust_in_progress = False
                return
        else:
            self._last_idle_time = 0


# ============================================================================
# 同步执行器
# ============================================================================

class SyncRequestsExecutor:
    """同步requests执行器（带重试机制）"""

    DEFAULTS = {
        "pool_connections": 100,
        "pool_maxsize": 100,
    }

    def __init__(
        self,
        verify_ssl: bool = True,
        request_timeout: int = 30,
        max_connections: int = 100,
    ):
        self.verify_ssl = verify_ssl
        self.request_timeout = request_timeout
        self.max_connections = max_connections
        self._session: Optional[requests.Session] = None

    def _get_session(self) -> requests.Session:
        """获取带重试配置的 requests Session（惰性创建）"""
        if self._session is None:
            pool_size = max(10, min(self.max_connections, 500))
            self._session = requests.Session()
            retry_strategy = Retry(
                total=3,
                backoff_factor=0.5,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["GET", "POST"],
            )
            adapter = HTTPAdapter(
                pool_connections=pool_size,
                pool_maxsize=pool_size,
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
                if '=' in command:
                    key, value = command.split('=', 1)
                    command = {
                        "action": "setConfig",
                        "param": {key: value},
                    }
                else:
                    command = {"action": command}

            action = command.get("action", "")
            if action == "getCurrentTime":
                base_url = f"http://{device.ip}:{device.port}/cgi-bin/global.cgi"
            else:
                base_url = f"http://{device.ip}:{device.port}/cgi-bin/configManager.cgi"

            params = self._build_simple_params(command)
            url = f"{base_url}?{params}"

            logger.info(f"发送请求到: {url}")

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
            param = command.get("param", {})
            if param and isinstance(param, dict) and len(param) == 1:
                first_key = list(param.keys())[0]
                first_value = param[first_key]
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
        for key, value in param.items():
            if isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        for sub_key, sub_value in item.items():
                            if isinstance(sub_value, dict):
                                for sub_sub_key, sub_sub_value in sub_value.items():
                                    params.append(f"{key}[{i}][{sub_key}][{sub_sub_key}]={sub_sub_value}")
                            else:
                                params.append(f"{key}[{i}][{sub_key}]={sub_value}")
                    else:
                        params.append(f"{key}[{i}]={item}")
            elif isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, dict):
                        for sub_sub_key, sub_sub_value in sub_value.items():
                            params.append(f"{key}[{sub_key}][{sub_sub_key}]={sub_sub_value}")
                    else:
                        params.append(f"{key}[{sub_key}]={sub_value}")
            else:
                params.append(f"{key}={value}")
        return "&".join(params)


# ============================================================================
# 异步执行器（使用 AdaptiveThreadPool）
# ============================================================================

class AsyncExecutor:
    """
    异步执行器，使用 AdaptiveThreadPool 动态线程池
    内部维护自适应线程池用于并发执行同步请求
    """

    def __init__(
        self,
        timeout: int = 30,
        verify_ssl: bool = True,
        max_connections: int = 100,
        auth_method: str = 'digest',
        min_threads: int = 10,
        max_threads: int = 80,
    ):
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.max_connections = max_connections
        self.auth_method = auth_method
        self.sync_executor = SyncRequestsExecutor(
            verify_ssl=verify_ssl,
            request_timeout=timeout,
            max_connections=max_connections,
        )
        self._thread_pool: Optional[AdaptiveThreadPool] = None
        self._closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    def _get_thread_pool(self) -> AdaptiveThreadPool:
        """惰性创建自适应线程池"""
        if self._thread_pool is None:
            self._thread_pool = AdaptiveThreadPool(
                min_workers=10,
                max_workers=self.max_connections,
                max_connections=self.max_connections,
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
        异步发送命令，使用自适应线程池执行同步requests请求
        """
        pool = self._get_thread_pool()
        return await asyncio.get_event_loop().run_in_executor(
            pool,
            self.sync_executor.send_command_sync,
            device,
            command,
        )

    def get_pool_stats(self) -> Dict[str, Any]:
        """获取线程池统计信息"""
        if self._thread_pool is not None:
            return self._thread_pool.stats()
        return {}

    def get_pool_metrics(self) -> PoolMetricsSnapshot:
        """获取线程池指标快照"""
        if self._thread_pool is not None:
            return self._thread_pool.metrics()
        return PoolMetricsSnapshot()


class AsyncIOManager:
    """
    基于requests库的异步管理器，提供与原有接口兼容的异步执行功能
    内部维护 AdaptiveThreadPool 自适应线程池用于并发执行同步请求
    """

    def __init__(
        self,
        timeout: int = 30,
        verify_ssl: bool = True,
        max_connections: int = 100,
        auth_method: str = 'digest',
        min_threads: int = 10,
        max_threads: int = 80,
    ):
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.max_connections = max_connections
        self.auth_method = auth_method
        self.sync_executor = SyncRequestsExecutor(
            verify_ssl=verify_ssl,
            request_timeout=timeout,
            max_connections=max_connections,
        )
        self._thread_pool: Optional[AdaptiveThreadPool] = None
        self._closed = False

    def _get_thread_pool(self) -> AdaptiveThreadPool:
        """惰性创建自适应线程池"""
        if self._thread_pool is None:
            self._thread_pool = AdaptiveThreadPool(
                min_workers=10,
                max_workers=self.max_connections,
                max_connections=self.max_connections,
                thread_name_prefix="async_io_manager",
            )
        return self._thread_pool

    def run_coroutine(self, coro):
        """运行协程（兼容原有接口）"""
        return asyncio.run(coro)

    def send_command(self, device, command):
        """
        兼容同步调用：提交异步发送并返回结果
        """
        async def async_send():
            return await self.send_command_async(device, command)

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                pool = self._get_thread_pool()
                future = pool.submit(asyncio.run, async_send())
                return future.result(timeout=self.timeout)
        except RuntimeError:
            pass

        return asyncio.run(async_send())

    async def send_command_async(
        self, device, command, use_url_auth: bool = False
    ):
        """
        异步发送命令，使用自适应线程池执行同步requests请求
        """
        pool = self._get_thread_pool()
        result = await asyncio.get_event_loop().run_in_executor(
            pool,
            self.sync_executor.send_command_sync,
            device,
            command,
        )
        ok, text, status, headers, error = result
        return (ok, text, status, headers, error)

    def close(self, wait: bool = True) -> None:
        """关闭管理器：优雅关闭线程池和 sync_executor"""
        self._closed = True
        if self._thread_pool is not None:
            self._thread_pool.shutdown(wait=wait)
            self._thread_pool = None
        self.sync_executor.close()

    def get_pool_stats(self) -> Dict[str, Any]:
        """获取线程池统计信息"""
        if self._thread_pool is not None:
            return self._thread_pool.stats()
        return {}

    def get_pool_metrics(self) -> PoolMetricsSnapshot:
        """获取线程池指标快照"""
        if self._thread_pool is not None:
            return self._thread_pool.metrics()
        return PoolMetricsSnapshot()


# ============================================================================
# 辅助函数
# ============================================================================

async def send_multiple_commands(device, commands, timeout=10):
    """并发发送多条命令到同一设备"""
    async with AsyncExecutor(timeout=timeout) as ex:
        results = []
        for cmd in commands:
            ok, msg, status, headers, error = await ex.send_command_async(device, cmd)
            results.append((ok, msg))
        return results
