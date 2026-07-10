#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设备管理模块 - 从 V9.4.1 复制并集成 AsyncIO 支持 (V9.5)
此文件基本保留 V9.4.1 的实现，但在 ConfigExecutor 中新增 `use_async` 选项，
并在可用时通过 `AsyncIOManager` 提交异步 CGI 请求以实现可取消、可并发的异步 I/O。
"""

import os
import platform
import subprocess
import threading
import concurrent.futures
import re
import asyncio
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Callable
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
import urllib3

# 引入我们在 V9.5 中新增的 AsyncIO 管理器
from utils.async_executor import AsyncIOManager

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ============================================================================
# 数据类定义
# ============================================================================

@dataclass
class DeviceInfo:
    """设备信息"""
    index: int
    ip: str
    port: str = "80"
    username: str = "admin"
    password: str = ""
    status: str = "未检测"
    online: bool = False
    selected: bool = True
    variables: Dict[str, str] = field(default_factory=dict)
    result: Optional[Dict] = None
    excel_row: int = 0
    last_message: str = ""
    
    def get_display_info(self) -> str:
        """获取显示信息"""
        info = f"{self.ip}:{self.port}"
        if self.variables.get("设备名称"):
            info = f"{self.variables['设备名称']} ({info})"
        return info


# ============================================================================
# 设备加载器
# ============================================================================

class DeviceLoader:
    """设备加载器"""
    
    def __init__(self, log_manager) -> None:
        self.log_manager = log_manager
        self.devices: List[DeviceInfo] = []
        self.excel_source_file = ""
        self.loaded_time = None
    
    def load_from_excel(self, file_path: str, mode: str = "standard") -> tuple:
        """从Excel加载设备"""
        try:
            self.log_manager.log_detailed(f"开始加载Excel文件: {file_path}", "INFO")
            
            self.excel_source_file = file_path
            self.loaded_time = datetime.now()
            
            # 读取Excel
            df = pd.read_excel(file_path, dtype=str, sheet_name='设备导入')
            total_rows = len(df)
            
            if total_rows == 0:
                raise ValueError("Excel文件为空")
            
            self.log_manager.log_detailed(f"Excel文件读取完成，共{total_rows}行", "INFO")
            
            self.devices.clear()
            column_mapping = self._analyze_columns(df, strict_mode=True)
            
            valid_rows = 0
            seen_ips = set()
            duplicate_ips = []
            for idx, row in df.iterrows():
                device = self._parse_row(idx, row, column_mapping, mode)
                if device:
                    # 重复IP检测
                    if device.ip in seen_ips:
                        msg = "第" + str(idx + 2) + "行设备IP重复: " + device.ip + "，已跳过"
                        self.log_manager.log_detailed(msg, "WARNING")
                        duplicate_ips.append(device.ip)
                        continue
                    seen_ips.add(device.ip)
                    # 将设备index规范为在解析后列表中的顺序索引，
                    # 保证 DeviceInfo.index 与 self.devices 的下标一致，
                    # 以便UI和进度回调可以使用 device.index 安全定位主列表中的设备。
                    device.excel_row = idx + 2
                    device.index = len(self.devices)
                    self.devices.append(device)
                    valid_rows += 1

            if duplicate_ips:
                unique_dup = sorted(set(duplicate_ips))
                ips_str = ", ".join(unique_dup)
                msg = "检测到 " + str(len(unique_dup)) + " 个重复IP地址: " + ips_str + "，已自动跳过重复行"
                self.log_manager.log_detailed(msg, "WARNING")
            
            self.log_manager.log_detailed(f"成功解析 {valid_rows} 台有效设备", "INFO")
            
            return self.devices, valid_rows
            
        except Exception as e:
            error_msg = f"加载Excel失败: {str(e)}"
            self.log_manager.log_detailed(error_msg, "ERROR")
            raise
    
    def _analyze_columns(self, df, strict_mode=False) -> dict:
        """分析Excel列结构
        
        Args:
            df: pandas DataFrame
            strict_mode: 如果True，要求精确匹配表头IP地址|端口|用户名|密码，
                         不匹配则抛ValueError。默认False保留模糊匹配，用于测试兼容。
        
        Returns:
            dict: 列名映射
        """
        if strict_mode:
            expected = ['IP地址', '端口', '用户名', '密码']
            actual = [str(col).strip() for col in df.columns]
            
            # 检查是否为4列且精确匹配
            if len(actual) < 4:
                raise ValueError(
                    f"模板列数不足，需要至少4列（IP地址 | 端口 | 用户名 | 密码），"
                    f"当前{len(actual)}列: {actual}"
                )
            
            # 取前4列检查
            for i, exp in enumerate(expected):
                if i < len(actual) and actual[i] != exp:
                    raise ValueError(
                        f"模板列名不匹配：第{i+1}列应为'{exp}'，"
                        f"实际为'{actual[i]}'。请下载标准模板。"
                    )
            
            return {
                'ip': expected[0],
                'port': expected[1],
                'username': expected[2],
                'password': expected[3],
            }
        
        # 原始模糊匹配逻辑
        column_mapping = {}
        
        column_patterns = {
            'ip': ['IP地址', 'IP', 'ip', '地址', '摄像机IP', '设备IP', '摄像头IP'],
            'port': ['端口', 'Port', 'port', '端口号', 'HTTP端口'],
            'username': ['用户名', 'User', 'user', '登录名', '管理员'],
            'password': ['密码', 'Password', 'password', '登录密码', 'pass']
        }
        
        for col_type, patterns in column_patterns.items():
            found = False
            for pattern in patterns:
                for excel_col in df.columns:
                    if str(excel_col).strip().lower() == pattern.lower():
                        column_mapping[col_type] = excel_col
                        found = True
                        break
                if found:
                    break
            
            if not found and col_type in df.columns:
                column_mapping[col_type] = col_type
        
        return column_mapping
    
    def _parse_row(self, idx, row, column_mapping, mode) -> Optional[object]: # type: ignore[return]
        """解析单行数据

        校验规则:
        - IP地址必须为有效IPv4格式 (x.x.x.x)
        - 端口号必须在 1-65535 范围内
        - 密码不能为空（记录警告但不跳过行）
        """
        try:
            ip_col = column_mapping.get('ip')
            port_col = column_mapping.get('port')
            user_col = column_mapping.get('username')
            pass_col = column_mapping.get('password')

            ip = str(row[ip_col]).strip() if ip_col and pd.notna(row.get(ip_col, '')) else ""
            port = str(row[port_col]).strip() if port_col and pd.notna(row.get(port_col, '')) else "80"
            username = str(row[user_col]).strip() if user_col and pd.notna(row.get(user_col, '')) else "admin"
            password = str(row[pass_col]).strip() if pass_col and pd.notna(row.get(pass_col, '')) else ""

            if not ip or ip.lower() in ["nan", "none", "", "null"]:
                return None

            # 校验IPv4地址格式
            ip_pattern = r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'
            if not re.match(ip_pattern, ip):
                self.log_manager.log_detailed(f"第{idx+2}行IP格式无效: {ip}", "WARNING")
                return None

            # 校验每个IP段范围 0-255
            parts = ip.split('.')
            if not all(0 <= int(p) <= 255 for p in parts):
                self.log_manager.log_detailed(f"第{idx+2}行IP段超出范围(0-255): {ip}", "WARNING")
                return None

            # 校验端口范围
            try:
                port_int = int(port)
                if port_int < 1 or port_int > 65535:
                    self.log_manager.log_detailed(f"第{idx+2}行端口号超出范围(1-65535): {port}", "WARNING")
                    return None
            except ValueError:
                self.log_manager.log_detailed(f"第{idx+2}行端口号格式无效: {port}", "WARNING")
                return None

            # 密码空值校验（日志警告但不跳过行）
            if not password:
                self.log_manager.log_detailed(f"第{idx+2}行设备 {ip} 密码为空，将使用空密码尝试连接", "WARNING")

            device = DeviceInfo(
                index=idx,
                ip=ip,
                port=str(port_int),
                username=username,
                password=password,
                status="未检测"
            )

            if mode == "customized" and device.variables:
                device.variables = self._extract_variables(row)

            return device

        except ValueError as e:
            self.log_manager.log_detailed(f"解析第{idx+2}行数据校验失败: {e}", "WARNING")
            return None
        except Exception as e:
            self.log_manager.log_detailed(f"解析第{idx+2}行失败: {e}", "WARNING")
            return None
    
    def _extract_variables(self, row) -> dict:
        """提取变量"""
        variables = {}
        for col, value in row.items():
            if pd.notna(value):
                str_value = str(value).strip()
                if str_value:
                    variables[col] = str_value
        return variables


# ============================================================================
# 设备检测器
# ============================================================================

class DeviceDetector:
    """设备检测器"""
    
    def __init__(self, config, log_manager, log_callback=None) -> None:
        self.config = config
        self.log_manager = log_manager
        self.log_callback = log_callback
        self.ping_concurrent = config.get("ping_concurrent", 100)
        self.ping_timeout = config.get("ping_timeout", 100)
        self.config_concurrent = config.get("config_concurrent", 5)
        self.ping_count = 1
    
    def _log(self, message, level="INFO") -> None:
        """统一的GUI日志记录方法 - 仅用于显示处理后的进度信息"""
        # 过滤进度相关的日志
        if "进度" in message and level in ["DEBUG", "INFO"]:
            return
            
        # 调用日志回调（仅显示到GUI）
        if self.log_callback:
            try:
                self.log_callback(message, level)
            except Exception as cb_err:
                self.log_manager.log_detailed(f"日志回调异常: {cb_err}", "ERROR")
        
        # 注意：这里不记录到文件，因为GUI日志应该是处理后的进度信息
    
    def detect_devices(self, devices, progress_callback=None, stop_callback=None) -> tuple:
        """纯Ping检测"""
        total_devices = len(devices)
        self._log(f"开始Ping检测 {total_devices} 台设备", "INFO")
        
        online_count = 0
        completed = 0
        
        # 使用最大并发数进行Ping扫描
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.ping_concurrent) as executor:
            future_to_index = {}
            for i, device in enumerate(devices):
                future = executor.submit(self._fast_ping, device.ip)
                future_to_index[future] = i
            
            # 收集需要更新的设备信息
            devices_updated = []
            
            for i, future in enumerate(concurrent.futures.as_completed(future_to_index), 1):
                # 检查是否停止
                if stop_callback and stop_callback():
                    self._log("检测被用户停止", "WARNING")
                    break
                
                device_index = future_to_index[future]
                device = devices[device_index]
                
                try:
                    is_online = future.result(timeout=5)
                    
                    device.online = is_online
                    completed += 1
                    
                    if is_online:
                        online_count += 1
                        device.status = "在线"
                        device.last_message = "网络可达"
                        self._log(f"设备 {device.ip} Ping成功", "INFO")
                    else:
                        device.status = "离线"
                        device.last_message = "网络不可达"
                        self._log(f"设备 {device.ip} Ping失败", "WARNING")
                        # 记录离线设备到失败日志
                        self.log_manager.log_failure(device, "设备离线，无法进行配置")
                        
                except concurrent.futures.TimeoutError:
                    device.online = False
                    device.status = "检测超时"
                    device.last_message = "Ping检测超时"
                    completed += 1
                    self._log(f"设备 {device.ip} Ping检测超时", "WARNING")
                except Exception as e:
                    device.online = False
                    device.status = "检测异常"
                    device.last_message = f"Ping检测异常: {str(e)[:50]}"
                    completed += 1
                    self._log(f"设备 {device.ip} Ping检测异常: {e}", "ERROR")
                
                # 收集更新信息
                devices_updated.append({
                    'index': device_index,
                    'status': device.status,
                    'online': device.online,
                    'message': device.last_message
                })
                
                # 每完成10个设备或达到100%时更新进度
                if completed % 10 == 0 or completed == total_devices:
                    # 更新进度
                    if progress_callback:
                        progress = (completed / total_devices) * 100 if total_devices > 0 else 0
                        stats = {
                            "completed": completed,
                            "total": total_devices,
                            "success": online_count,
                            "failed": completed - online_count,
                            "devices_updated": devices_updated
                        }
                        progress_callback("ping_only", progress, stats)
                        devices_updated = []  # 清空已更新的设备列表
        
        offline_count = total_devices - online_count
        self._log(f"Ping检测完成: {online_count}台在线, {offline_count}台离线", "INFO")
        
        return online_count, offline_count
    
    def _fast_ping(self, ip) -> bool:
        """快速Ping检测"""
        try:
            if platform.system().lower() == "windows":
                command = ["ping", "-n", str(self.ping_count), "-w", str(self.ping_timeout), ip]
            else:
                command = ["ping", "-c", str(self.ping_count), "-W", str(self.ping_timeout/1000), ip]
            
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False
            )
            
            process_timeout = min(self.ping_timeout/1000 + 0.5, 2.0)
            stdout, stderr = process.communicate(timeout=process_timeout)
            
            output = stdout.decode(
                'gbk' if platform.system().lower() == "windows" else 'utf-8', 
                errors='ignore'
            ).lower()
            
            # 判断是否成功
            success_keywords = ["bytes=", "ttl=", "reply from", "来自", "time="]
            is_success = process.returncode == 0 or any(kw in output for kw in success_keywords)
            
            return is_success
                
        except subprocess.TimeoutExpired:
            return False
            
        except Exception as e:
            return False


# ============================================================================
# 配置执行器
# ============================================================================

class ConfigExecutor:
    """配置执行器 - v9.4.8 严格设备状态管理，扩展为支持异步发送"""
    
    def __init__(self, config, log_manager, log_callback=None, use_async=False) -> None:
        self.config = config
        self.log_manager = log_manager
        self.log_callback = log_callback
        self.config_concurrent = config.get("config_concurrent", 30)
        self.timeout = config.get("timeout", 3000) / 1000.0
        self.verify_ssl = config.get('verify_ssl', True)
        self.auth_method = config.get("auth_method", "digest")
        self.session = self._create_session()
        self._stop_flag = threading.Event()  # 停止标志
        self._executor = None  # 线程池引用
        self._futures = []  # 所有future任务
        self._completed_tasks = 0  # 已完成的任务数
        self._total_tasks = 0  # 总任务数
        self._progress_lock = threading.Lock()  # 进度锁
        self._device_locks = {}  # 设备锁字典，确保每个设备只有一个线程处理
        self._device_processing = set()  # 正在处理的设备集合
        self._device_lock = threading.Lock()  # 设备集合的锁
        # 异步执行相关
        self.use_async = use_async
        self.async_manager = None
        self._async_semaphore = None  # 共享的异步信号量
        self._async_command_semaphore = None  # 命令级别的信号量
        if self.use_async:
            try:
                # AsyncIOManager — 使用自适应线程池
                max_conns = config.get("max_connections", 100)
                self.async_manager = AsyncIOManager(
                    timeout=self.timeout,
                    verify_ssl=self.config.get('verify_ssl', True),
                    max_connections=max_conns,
                    auth_method=self.auth_method,
                )
                self._async_semaphore = asyncio.Semaphore(self.config_concurrent)  # 设备级别的共享信号量
                self._async_command_semaphore = asyncio.Semaphore(self.config_concurrent * 2)  # 命令级别的信号量，允许更多并发
                self._log(f"AsyncIOManager 已初始化（自适应线程池，max_connections={max_conns}），设备并发数: {self.config_concurrent}，命令并发数: {self.config_concurrent * 2}", "DEBUG")
            except Exception:
                self._log("初始化 AsyncIOManager 失败，回退到同步模式", "WARNING")
                self.async_manager = None

    def _log(self, message, level="INFO") -> None:
        """统一的日志记录方法"""
        # 过滤进度相关的日志
        if "进度" in message and level in ["DEBUG", "INFO"]:
            return
            
        # 调用日志回调
        if self.log_callback:
            try:
                self.log_callback(message, level)
            except Exception as cb_err:
                self.log_manager.log_detailed(f"日志回调异常: {cb_err}", "ERROR")
        
        # 记录到文件
        if self.log_manager:
            self.log_manager.log_detailed(message, level)

    def _create_session(self) -> requests.Session:
        """创建HTTP会话"""
        session = requests.Session()
        retry_strategy = Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(
            pool_connections=100,
            pool_maxsize=100,
            max_retries=retry_strategy
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def stop(self) -> None:
        """停止配置 - 完全停止"""
        self._log("正在停止所有配置任务...", "WARNING")
        self._stop_flag.set()
        # 立即关闭会话以中断可能正在进行的阻塞HTTP请求
        try:
            if self.session:
                try:
                    self.session.close()
                    self._log("HTTP session 已关闭以中断请求", "DEBUG")
                except Exception:
                    pass
        except Exception:
            pass

        # 关闭异步管理器（如果存在）以中断异步请求
        try:
            if self.async_manager:
                try:
                    self.async_manager.close()
                    self._log("AsyncIOManager 已关闭", "DEBUG")
                except Exception:
                    pass
        except Exception:
            pass

        # 取消所有未完成的future任务
        if self._futures:
            cancelled_count = 0
            for future in self._futures:
                if not future.done():
                    future.cancel()
                    cancelled_count += 1
            self._log(f"已取消 {cancelled_count} 个配置任务", "WARNING")
        
        # 关闭线程池
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._log("线程池已关闭", "WARNING")

    def _is_stopped(self) -> bool:
        """检查是否已停止"""
        return self._stop_flag.is_set()

    def _check_and_mark_device_processing(self, device) -> bool:
        """检查并标记设备为处理中（线程安全）"""
        with self._device_lock:
            if device.ip in self._device_processing:
                return False  # 设备已经在处理中
            self._device_processing.add(device.ip)
            return True

    def _unmark_device_processing(self, device) -> None:
        """取消设备的处理标记（线程安全）"""
        with self._device_lock:
            if device.ip in self._device_processing:
                self._device_processing.remove(device.ip)

    def _is_device_eligible_for_config(self, device) -> bool:
        """检查设备是否符合配置条件（严格检查）"""
        # 检查设备在线状态
        if not device.online:
            return False
        
        # 检查设备状态
        if device.status not in ["在线", "等待配置", "正在配置"]:
            return False
        
        # 检查设备是否被选中
        if not device.selected:
            return False
        
        # 检查设备是否已经在处理中
        with self._device_lock:
            if device.ip in self._device_processing:
                return False
        
        return True

    def _configure_device_strict_wrapper(self, device, mode="standard", progress_callback=None) -> dict:
        """设备配置的包装方法，确保异常时清理标记"""
        try:
            result = self._configure_device_strict(device, mode, progress_callback)
            return result
        except Exception as e:
            self._log(f"设备 {device.ip} 配置包装方法异常: {e}", "ERROR")
            # 确保清理设备标记
            self._unmark_device_processing(device)
            raise

    def _cleanup_device_processing(self) -> None:
        """清理所有设备处理标记"""
        with self._device_lock:
            self._device_processing.clear()

    def execute_batch(self, devices, mode="standard", exec_strategy="device_first", 
                     progress_callback=None, stop_callback=None, total_tasks=None) -> dict:
        """批量执行配置 - 严格跳过离线设备"""
        # 重置停止标志
        self._stop_flag.clear()
        self._completed_tasks = 0
        self._futures = []
        
        # 严格筛选在线设备
        target_devices = []
        skipped_devices = []
        
        for device in devices:
            # 三重检查：online标志、状态、实际可达性
            if (device.online and 
                device.status in ["在线", "等待配置", "正在配置", "执行中"]):
                target_devices.append(device)
            else:
                skipped_devices.append(device)
                device.status = "离线"
                device.last_message = "设备离线，跳过配置"
                # 记录到失败日志
                self.log_manager.log_failure(device, "设备离线，跳过配置")
        
        total_target = len(target_devices)
        
        if skipped_devices:
            skipped_ips = [f"{d.ip}:{d.port}" for d in skipped_devices[:5]]
            self._log(f"严格跳过 {len(skipped_devices)} 台非在线设备", "WARNING")
            if len(skipped_ips) <= 10:
                self._log(f"跳过的设备: {', '.join(skipped_ips)}", "DEBUG")
        
        if total_target == 0:
            self._log("没有符合条件的在线设备可配置", "WARNING")
            return []
        
        self._log(f"开始配置 {total_target} 台符合条件的在线设备", "INFO")
        
        # 计算总任务数（只计算在线设备的命令）
        if total_tasks is None:
            base_commands = self.config.get("cgi_commands", [])
            if mode == "standard":
                # 标准模式：过滤掉包含变量的命令
                valid_commands = [cmd for cmd in base_commands if not re.search(r'\{([^}]+)\}', cmd)]
            else:
                valid_commands = base_commands
            self._total_tasks = len(valid_commands) * total_target
        else:
            self._total_tasks = total_tasks
        
        self._log(f"总配置任务数: {self._total_tasks} (仅在线设备)", "INFO")
        
        # 立即更新所有在线设备状态为"正在配置"，使用设备自身的索引保证与UI映射一致
        devices_updated = []
        for device in target_devices:
            device.status = "正在配置"
            device.last_message = "开始执行配置"
            devices_updated.append({
                'index': device.index,
                'status': device.status,
                'online': device.online,
                'message': device.last_message
            })
        
        # 初始进度更新
        if progress_callback:
            stats = {
                "completed": 0,
                "total": self._total_tasks,
                "success": 0,
                "failed": 0,
                "devices_updated": devices_updated
            }
            progress_callback("configuring", 0, stats)
        
        # 根据执行策略选择方法
        try:
            if self.use_async and self.async_manager:
                # 优先使用异步实现（device_first 模式支持）
                if exec_strategy == "device_first":
                    # run_coroutine 直接返回结果，不是 Future
                    result = self.async_manager.run_coroutine(self._async_execute_by_device(target_devices, mode, progress_callback, stop_callback))
                    return result
                else:
                    # 命令优先策略使用全并发异步版本
                    result = self.async_manager.run_coroutine(self._async_execute_by_command(target_devices, mode, progress_callback, stop_callback))
                    return result
            else:
                if exec_strategy == "device_first":
                    return self._execute_by_device_strict(target_devices, mode, progress_callback, stop_callback)
                else:
                    return self._execute_by_command_strict(target_devices, mode, progress_callback, stop_callback)
        finally:
            # 清理资源
            self._executor = None
            self._futures = []
            self._cleanup_device_processing()

    def _execute_by_device_strict(self, devices, mode="standard", progress_callback=None, stop_callback=None) -> dict:
        """严格版：按设备执行，只处理在线设备"""
        results = []
        total_devices = len(devices)
        
        self._log(f"使用设备优先策略，将处理 {total_devices} 台在线设备", "INFO")
        
        # 创建线程池
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.config_concurrent)
        
        # 提交所有设备任务
        for device in devices:
            # 提交前进行严格检查
            if not self._is_device_eligible_for_config(device):
                self._log(f"设备 {device.ip} 不符合配置条件，跳过配置", "WARNING")
                device.status = "跳过"
                device.last_message = "不符合配置条件"
                continue
                
            # 检查并标记设备为处理中
            if not self._check_and_mark_device_processing(device):
                self._log(f"设备 {device.ip} 已经在处理中，跳过重复提交", "WARNING")
                continue
                
            if self._is_stopped() or (stop_callback and stop_callback()):
                self._log("配置被停止，不再提交新任务", "WARNING")
                self._unmark_device_processing(device)  # 清理标记
                break
            
            future = self._executor.submit(self._configure_device_strict_wrapper, device, mode, progress_callback)
            self._futures.append(future)
        
        # 处理完成的任务
        for future in self._futures:
            # 检查停止标志
            if self._is_stopped() or (stop_callback and stop_callback()):
                self._log("配置被停止，等待剩余任务完成", "WARNING")
                break
            
            try:
                result = future.result(timeout=30)
                if result:
                    device = result['device']
                    device.result = result
                    results.append(result)
                    
                    # 更新设备显示信息
                    if result['total_commands'] > 0:
                        total_executed = result['success_commands'] + result['failed_commands']
                        device.last_message = f"完成: {total_executed}/{result['total_commands']}命令 (成功:{result['success_commands']}, 失败:{result['failed_commands']})"
                        
                        # 如果有失败命令，记录到失败日志
                        if result['failed_commands'] > 0:
                            failure_msg = f"{result['failed_commands']}条命令执行失败"
                            if result.get('failure_details'):
                                failure_msg += f": {result['failure_details']}"
                            self.log_manager.log_failure(device, failure_msg)
                    
                    # 清理设备处理标记
                    self._unmark_device_processing(device)
                    
            except concurrent.futures.CancelledError:
                self._log("任务被取消", "WARNING")
            except Exception as e:
                self._log(f"设备任务异常: {e}", "ERROR")
                # 清理设备处理标记
                if 'device' in locals():
                    self._unmark_device_processing(device)
        
        # 关闭线程池
        if self._executor:
            self._executor.shutdown(wait=True)
        
        # 清理所有设备标记
        self._cleanup_device_processing()
        
        # 最终进度更新
        if progress_callback:
            total_executed = sum(r['success_commands'] + r['failed_commands'] for r in results)
            stats = {
                "completed": total_executed,
                "total": self._total_tasks,
                "success": sum(r['success_commands'] for r in results),
                "failed": sum(r['failed_commands'] for r in results),
                "devices_updated": self._get_devices_update_info(devices)
            }
            progress_callback("configuring", 100, stats)
        
        total_executed = sum(r['success_commands'] + r['failed_commands'] for r in results)
        completion_rate = (total_executed / self._total_tasks * 100) if self._total_tasks > 0 else 0
        self._log(f"配置完成: {total_executed}/{self._total_tasks}命令执行完成 ({completion_rate:.1f}%完成率)", "INFO")
        
        return results
    
    def _configure_device_strict(self, device, mode="standard", progress_callback=None) -> dict:
        """严格版：为设备执行配置，确保设备在线"""
        start_time = datetime.now()
        
        try:
            # 严格检查设备是否在线
            if not (device.online and device.status in ["在线", "正在配置", "等待配置"]):
                self._log(f"设备 {device.ip} 不在线或状态异常，跳过配置", "WARNING")
                device.status = "离线"
                device.last_message = "设备不在线，跳过配置"
                
                # 记录到失败日志
                self.log_manager.log_failure(device, "设备不在线，跳过配置")
                
                return {
                    'device': device,
                    'ip': device.ip,
                    'port': device.port,
                    'success': False,
                    'total_commands': 0,
                    'success_commands': 0,
                    'failed_commands': 0,
                    'failure_details': "设备不在线",
                    'start_time': start_time.strftime("%H:%M:%S"),
                    'end_time': datetime.now().strftime("%H:%M:%S"),
                    'total_time': 0
                }
            
            base_commands = self.config.get("cgi_commands", [])
            
            if mode == "customized" and device.variables:
                commands = []
                for base_cmd in base_commands:
                    custom_cmd = self._generate_custom_command(base_cmd, device.variables)
                    if custom_cmd:
                        commands.append(custom_cmd)
            else:
                # 标准模式，过滤掉包含变量的命令
                commands = [cmd for cmd in base_commands if not re.search(r'\{([^}]+)\}', cmd)]
            
            total_commands = len(commands)
            success_count = 0
            failed_count = 0
            failure_details = []
            
            self._log(f"设备 {device.ip} 开始执行 {total_commands} 条命令", "INFO")
            
            # 立即更新设备状态
            device.status = "执行中"
            device.last_message = f"执行第1/{total_commands}条命令"
            
            for i, command in enumerate(commands, 1):
                # 检查停止标志
                if self._is_stopped():
                    self._log(f"设备 {device.ip} 配置被停止，剩余 {total_commands - i + 1} 条命令未执行", "WARNING")
                    device.status = "已停止"
                    device.last_message = f"已停止，完成 {i-1}/{total_commands}条命令"
                    break
                
                # 每次命令前再次检查设备状态
                if not device.online:
                    self._log(f"设备 {device.ip} 在执行过程中变为离线，停止配置", "WARNING")
                    device.status = "离线"
                    device.last_message = f"执行过程中离线，完成 {i-1}/{total_commands}条命令"
                    break
                
                try:
                    # 更新设备状态
                    device.last_message = f"执行第{i}/{total_commands}条命令"
                    
                    # 发送命令
                    success, message = self._send_command(device, command, i, total_commands)
                    
                    # 更新进度和统计
                    with self._progress_lock:
                        self._completed_tasks += 1
                        if success:
                            success_count += 1
                        else:
                            failed_count += 1
                            failure_details.append(f"命令{i}: {message}")
                    
                    # 记录失败到失败日志
                    if not success:
                        self.log_manager.log_failure(device, f"命令执行失败: {message}", command)
                    
                    # 立即更新进度
                    if progress_callback:
                        progress = (self._completed_tasks / self._total_tasks * 100) if self._total_tasks > 0 else 0
                        
                        stats = {
                            "completed": self._completed_tasks,
                            "total": self._total_tasks,
                            "success": success_count,
                            "failed": failed_count,
                            "devices_updated": [{
                                'index': device.index,
                                'status': device.status,
                                'online': device.online,
                                'message': device.last_message
                            }]
                        }
                        progress_callback("configuring", progress, stats)
                        
                except Exception as e:
                    error_msg = f"命令{i} ({command[:50]}...): {str(e)[:100]}"
                    failure_details.append(error_msg)
                    with self._progress_lock:
                        failed_count += 1
                        self._completed_tasks += 1
                    
                    # 记录异常到失败日志
                    self.log_manager.log_failure(device, f"命令执行异常: {error_msg}", command)
                    self._log(f"设备 {device.ip} 命令 {i} 执行异常: {e}", "ERROR")
            
            # 计算完成率和成功率
            completed_count = success_count + failed_count
            completion_rate = (completed_count / total_commands * 100) if total_commands > 0 else 0
            success_rate = (success_count / total_commands * 100) if total_commands > 0 else 0
            
            # 更新设备最终状态
            if self._is_stopped():
                device.status = "已停止"
                device.last_message = f"已停止，完成 {completed_count}/{total_commands}条命令"
            elif not device.online:
                device.status = "离线"
                device.last_message = f"执行过程中离线，完成 {completed_count}/{total_commands}条命令"
            elif completed_count == total_commands:
                if success_count > 0:
                    device.status = "成功"
                    device.last_message = f"完成: {completed_count}/{total_commands}命令 (成功:{success_count}, 失败:{failed_count})"
                else:
                    device.status = "失败"
                    device.last_message = f"完成: {completed_count}/{total_commands}命令 (成功:{success_count}, 失败:{failed_count})"
            else:
                device.status = "部分完成"
                device.last_message = f"部分完成: {completed_count}/{total_commands}条命令"
            
            result = {
                'device': device,
                'ip': device.ip,
                'port': device.port,
                'success': success_count > 0,
                'total_commands': total_commands,
                'success_commands': success_count,
                'failed_commands': failed_count,
                'failure_details': "; ".join(failure_details[:3]) if failure_details else None,
                'start_time': start_time.strftime("%H:%M:%S"),
                'end_time': datetime.now().strftime("%H:%M:%S"),
                'total_time': (datetime.now() - start_time).total_seconds()
            }
            
            log_level = "SUCCESS" if success_count > 0 else "WARNING"
            self._log(f"设备 {device.ip} 配置完成: {completed_count}/{total_commands}命令执行完成 (成功:{success_count}, 失败:{failed_count})", log_level)
            
            return result
            
        except Exception as e:
            self._log(f"设备 {device.ip} 配置异常: {e}", "ERROR")
            
            # 记录异常到失败日志
            self.log_manager.log_failure(device, f"配置异常: {str(e)[:100]}")
            
            # 确保清理设备标记
            self._unmark_device_processing(device)
            
            return {
                'device': device,
                'ip': device.ip,
                'port': device.port,
                'success': False,
                'total_commands': 0,
                'success_commands': 0,
                'failed_commands': 0,
                'failure_details': f"配置异常: {str(e)[:100]}",
                'start_time': start_time.strftime("%H:%M:%S"),
                'end_time': datetime.now().strftime("%H:%M:%S"),
                'total_time': (datetime.now() - start_time).total_seconds()
            }

    def _execute_by_command_strict(self, devices, mode="standard", progress_callback=None, stop_callback=None) -> dict:
        """严格版：按命令执行，只处理在线设备"""
        # 创建线程池
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.config_concurrent)
        
        # 创建结果容器（只包含在线设备）
        online_devices = [d for d in devices if d.online and d.status in ["在线", "正在配置", "等待配置"]]
        total_devices = len(online_devices)
        
        base_commands = self.config.get("cgi_commands", [])
        
        if not base_commands:
            self._log("没有配置CGI命令", "ERROR")
            return []
        
        self._log(f"使用命令优先策略，将执行 {len(base_commands)} 条命令到 {total_devices} 台在线设备", "INFO")
        
        results = []
        for device in online_devices:
            results.append({
                'device': device,
                'ip': device.ip,
                'port': device.port,
                'success': False,
                'total_commands': 0,
                'success_commands': 0,
                'failed_commands': 0,
                'failure_details': "",
                'start_time': datetime.now().strftime("%H:%M:%S"),
                'end_time': "",
                'total_time': 0
            })
        
        # 按命令执行
        for cmd_idx, base_cmd in enumerate(base_commands, 1):
            # 检查停止标志
            if self._is_stopped() or (stop_callback and stop_callback()):
                self._log("配置被停止", "WARNING")
                break
            
            self._log(f"执行命令 {cmd_idx}/{len(base_commands)}: {base_cmd}", "INFO")
            
            # 为每个在线设备生成命令
            device_commands = []
            for device in online_devices:
                # 每次命令前检查设备状态
                if not self._is_device_eligible_for_config(device):
                    self._log(f"设备 {device.ip} 状态异常，跳过命令执行", "WARNING")
                    continue
                    
                if mode == "customized" and device.variables:
                    # 生成自定义命令
                    custom_cmd = self._generate_custom_command(base_cmd, device.variables)
                    if custom_cmd:
                        device_commands.append((device, custom_cmd))
                else:
                    # 标准模式，检查是否包含变量
                    if not re.search(r'\{([^}]+)\}', base_cmd):
                        device_commands.append((device, base_cmd))
            
            if not device_commands:
                continue
            
            # 并发执行当前命令到所有设备
            command_futures = []
            for device, cmd in device_commands:
                future = self._executor.submit(self._send_command, device, cmd, cmd_idx, len(base_commands))
                command_futures.append((future, device, cmd))
                self._futures.append(future)
            
            # 处理结果
            for future, device, cmd in command_futures:
                # 检查停止标志
                if self._is_stopped() or (stop_callback and stop_callback()):
                    break
                
                try:
                    success, message = future.result(timeout=10)
                    
                    # 更新设备结果
                    device_index = online_devices.index(device)
                    results[device_index]['total_commands'] += 1
                    if success:
                        results[device_index]['success_commands'] += 1
                    else:
                        results[device_index]['failed_commands'] += 1
                        if results[device_index]['failure_details']:
                            results[device_index]['failure_details'] += "; "
                        results[device_index]['failure_details'] += f"命令{cmd_idx}: {message}"
                        
                        # 记录失败到失败日志
                        self.log_manager.log_failure(device, f"命令执行失败: {message}", cmd)
                    
                    # 更新进度
                    with self._progress_lock:
                        self._completed_tasks += 1
                    
                    # 更新设备状态
                    device.status = "执行中"
                    device.last_message = f"执行命令 {cmd_idx}/{len(base_commands)}"
                    
                    # 更新进度显示
                    if progress_callback:
                        progress = (self._completed_tasks / self._total_tasks * 100) if self._total_tasks > 0 else 0
                        stats = {
                            "completed": self._completed_tasks,
                            "total": self._total_tasks,
                            "success": sum(r['success_commands'] for r in results),
                            "failed": sum(r['failed_commands'] for r in results),
                            "devices_updated": self._get_devices_update_info(online_devices)
                        }
                        progress_callback("configuring", progress, stats)
                        
                except concurrent.futures.CancelledError:
                    self._log("命令执行被取消", "WARNING")
                except Exception as e:
                    self._log(f"设备 {device.ip} 执行命令失败: {e}", "ERROR")
        
        # 关闭线程池
        if self._executor:
            self._executor.shutdown(wait=True)
        
        # 更新最终结果和设备状态
        end_time = datetime.now()
        for i, (result, device) in enumerate(zip(results, online_devices)):
            result['end_time'] = end_time.strftime("%H:%M:%S")
            start_time = datetime.strptime(result['start_time'], "%H:%M:%S")
            result['total_time'] = (end_time - start_time).total_seconds()
            
            # 只要执行了命令，无论成功失败都算完成
            total_executed = result['success_commands'] + result['failed_commands']
            if total_executed > 0:
                result['success'] = result['success_commands'] > 0
            else:
                result['success'] = False
            
            # 更新设备状态和显示信息
            if self._is_stopped():
                device.status = "已停止"
                device.last_message = f"已停止，完成 {total_executed}条命令"
            elif not device.online:
                device.status = "离线"
                device.last_message = f"执行过程中离线，完成 {total_executed}条命令"
            elif total_executed == result['total_commands']:
                if result['success']:
                    device.status = "成功"
                    device.last_message = f"完成: {total_executed}/{result['total_commands']}命令 (成功:{result['success_commands']}, 失败:{result['failed_commands']})"
                else:
                    device.status = "失败"
                    device.last_message = f"完成: {total_executed}/{result['total_commands']}命令 (成功:{result['success_commands']}, 失败:{result['failed_commands']})"
            else:
                device.status = "部分完成"
                device.last_message = f"完成: {total_executed}/{result['total_commands']}命令"
            
            device.result = result
        
        # 最终进度更新
        if progress_callback:
            total_executed = sum(r['success_commands'] + r['failed_commands'] for r in results)
            stats = {
                "completed": total_executed,
                "total": self._total_tasks,
                "success": sum(r['success_commands'] for r in results),
                "failed": sum(r['failed_commands'] for r in results),
                "devices_updated": self._get_devices_update_info(online_devices)
            }
            progress_callback("configuring", 100, stats)
        
        total_executed_commands = sum(r['success_commands'] + r['failed_commands'] for r in results)
        completion_rate = (total_executed_commands / self._total_tasks * 100) if self._total_tasks > 0 else 0
        self._log(f"命令优先策略执行完成: {total_executed_commands}/{self._total_tasks}命令执行完成 ({completion_rate:.1f}%完成率)", "INFO")
        
        return results

    def _get_devices_update_info(self, devices) -> list:
        """获取设备更新信息，返回使用设备自身索引以保持与主列表的一致性"""
        devices_updated = []
        for device in devices:
            devices_updated.append({
                'index': device.index,
                'status': device.status,
                'online': device.online,
                'message': device.last_message
            })
        return devices_updated


    # ====================== 异步实现 (asyncio) ==============================
    async def _async_config_device(self, device, mode="standard", progress_callback=None, semaphore=None) -> Optional[dict]:
        """异步版的设备配置方法"""
        start_time = datetime.now()
        
        try:
            # 检查设备状态
            if not self._is_device_eligible_for_config(device):
                self._log(f"设备 {device.ip} 不符合配置条件，跳过", "WARNING")
                return None
            
            # 获取命令列表
            base_commands = self.config.get("cgi_commands", [])
            
            if mode == "customized" and device.variables:
                commands = []
                for base_cmd in base_commands:
                    custom_cmd = self._generate_custom_command(base_cmd, device.variables)
                    if custom_cmd:
                        commands.append(custom_cmd)
            else:
                commands = [cmd for cmd in base_commands if not re.search(r'\{([^}]+)\}', cmd)]
            
            total_commands = len(commands)
            success_count = 0
            failed_count = 0
            failure_details = []
            
            self._log(f"[async] 设备 {device.ip} 开始执行 {total_commands} 条命令", "INFO")
            
            # 更新设备状态
            device.status = "执行中"
            device.last_message = f"执行第1/{total_commands}条命令" if total_commands > 0 else "无命令"
            
            # 逐条执行命令
            for i, command in enumerate(commands, 1):
                if self._is_stopped():
                    device.status = "已停止"
                    device.last_message = f"已停止，完成 {i-1}/{total_commands}条命令"
                    break
                
                if not device.online:
                    device.status = "离线"
                    device.last_message = f"执行过程中离线，完成 {i-1}/{total_commands}条命令"
                    break
                
                device.last_message = f"执行第{i}/{total_commands}条命令"
                
                # 控制并发
                if semaphore:
                    async with semaphore:
                        ok, message = await self._async_send_command_with_url_auth(device, command, i, total_commands)
                else:
                    ok, message = await self._async_send_command_with_url_auth(device, command, i, total_commands)
                
                # 更新统计
                if ok:
                    success_count += 1
                else:
                    failed_count += 1
                    failure_details.append(f"命令{i}: {message}")
                    self.log_manager.log_failure(device, f"命令执行失败: {message}", command)
                
                # 更新全局已完成计数
                self._completed_tasks += 1
                
                # 进度回调
                if progress_callback:
                    progress = (self._completed_tasks / self._total_tasks * 100) if self._total_tasks > 0 else 0
                    stats = {
                        "completed": self._completed_tasks,
                        "total": self._total_tasks,
                        "success": success_count,
                        "failed": failed_count,
                        "devices_updated": [{
                            'index': device.index,
                            'status': device.status,
                            'online': device.online,
                            'message': device.last_message
                        }]
                    }
                    try:
                        progress_callback("configuring", progress, stats)
                    except Exception:
                        pass
            
            # 最终更新设备状态
            completed_count = success_count + failed_count
            if self._is_stopped():
                device.status = "已停止"
                device.last_message = f"已停止，完成 {completed_count}/{total_commands}条命令"
            elif not device.online:
                device.status = "离线"
                device.last_message = f"执行过程中离线，完成 {completed_count}/{total_commands}条命令"
            elif completed_count == total_commands:
                device.status = "成功" if success_count > 0 else "失败"
                device.last_message = f"完成: {completed_count}/{total_commands}命令 (成功:{success_count}, 失败:{failed_count})"
            else:
                device.status = "部分完成"
                device.last_message = f"部分完成: {completed_count}/{total_commands}条命令"
            
            result = {
                'device': device,
                'ip': device.ip,
                'port': device.port,
                'success': success_count > 0,
                'total_commands': total_commands,
                'success_commands': success_count,
                'failed_commands': failed_count,
                'failure_details': "; ".join(failure_details[:3]) if failure_details else None,
                'start_time': start_time.strftime("%H:%M:%S"),
                'end_time': datetime.now().strftime("%H:%M:%S"),
                'total_time': (datetime.now() - start_time).total_seconds()
            }
            
            return result
            
        except Exception as e:
            self._log(f"设备 {device.ip} 异步配置异常: {e}", "ERROR")
            self.log_manager.log_failure(device, f"配置异常: {str(e)[:100]}")
            return {
                'device': device,
                'ip': device.ip,
                'port': device.port,
                'success': False,
                'total_commands': 0,
                'success_commands': 0,
                'failed_commands': 0,
                'failure_details': f"配置异常: {str(e)[:100]}",
                'start_time': start_time.strftime("%H:%M:%S"),
                'end_time': datetime.now().strftime("%H:%M:%S"),
                'total_time': (datetime.now() - start_time).total_seconds()
            }

    async def _async_send_command_with_url_auth(self, device, command, cmd_index, total_commands) -> tuple:
        """使用URL认证方式发送命令"""
        try:
            # 构建带认证信息的URL
            username = device.username if hasattr(device, 'username') else 'admin'
            password = device.password if hasattr(device, 'password') else 'admin'
            
            base_url = f"http://{username}:{password}@{device.ip}:{device.port}/cgi-bin/configManager.cgi"
            encoded_cmd = requests.utils.quote(command, safe='')
            display_cmd = encoded_cmd.replace('%20', ' ')
            full_url = f"{base_url}?action=setConfig&{encoded_cmd}"
            display_url = f"http://{username}:****@{device.ip}:{device.port}/cgi-bin/configManager.cgi?action=setConfig&{display_cmd}"
            
            # 显示GUI进度信息
            self._log(f"设备 {device.ip} CGI请求 {cmd_index}/{total_commands}: {display_url}", "INFO")
            
            # 记录原始请求信息
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Accept': '*/*',
                'Connection': 'close'
            }
            self.log_manager.log_cgi_request(
                device.ip, cmd_index, total_commands, full_url, "URL_Auth", headers, raw_command=command
            )
            
            # 记录开始时间
            request_start = datetime.now()
            
            # 使用AsyncIOManager发送请求（启用URL认证）
            result = await self.async_manager.send_command_async(device, command, use_url_auth=True)
            
            # 解析结果
            if len(result) == 5:
                ok, message, status_code, response_headers, response_body = result
            else:
                ok, message = result
                status_code = 200 if ok else "ASYNC_ERROR"
                response_headers = {}
                response_body = message
            
            # 计算响应时间
            request_time = (datetime.now() - request_start).total_seconds()
            
            # 记录响应信息
            if ok:
                self.log_manager.log_cgi_response(
                    device.ip, status_code, request_time, response_headers, 
                    response_body, success=True, raw_command=command
                )
                self._log(f"设备 {device.ip} CGI响应: 状态码={status_code}, 耗时={request_time:.2f}s", "INFO")
            else:
                self.log_manager.log_cgi_response(
                    device.ip, status_code, request_time, response_headers, 
                    response_body, success=False, raw_command=command
                )
                self._log(f"设备 {device.ip} HTTP错误 {status_code}, 耗时={request_time:.2f}s", "ERROR")
            
            return ok, message
            
        except Exception as e:
            error_msg = f"URL认证请求异常: {e}"
            self._log(f"设备 {device.ip} {error_msg}", "ERROR")
            return False, error_msg

    async def _async_execute_by_device(self, devices, mode="standard", progress_callback=None, stop_callback=None) -> dict:
        """异步版的设备优先执行逻辑，在 AsyncIOManager 的事件循环中执行。"""
        results = []
        total_devices = len(devices)
        self._log(f"[async] 使用设备优先策略，将处理 {total_devices} 台在线设备", "INFO")

        # 并发控制
        semaphore = asyncio.Semaphore(self.config_concurrent)

        # 重置计数
        self._completed_tasks = 0

        # 创建并发任务
        tasks = []
        for device in devices:
            # 再次检查是否符合条件
            if not self._is_device_eligible_for_config(device):
                self._log(f"设备 {device.ip} 不符合配置条件，跳过", "WARNING")
                continue

            device.status = "正在配置"
            device.last_message = "开始执行配置"

            task = asyncio.create_task(self._async_config_device(device, mode, progress_callback, semaphore))
            tasks.append(task)

        if not tasks:
            self._log("没有任务需要执行 (async)", "WARNING")
            return []

        # 等待所有任务完成
        done, pending = await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)

        for t in done:
            try:
                res = t.result()
                if res:
                    results.append(res)
            except Exception as e:
                self._log(f"异步任务异常: {e}", "ERROR")

        # 最终进度回调
        if progress_callback:
            total_executed = sum(r['success_commands'] + r['failed_commands'] for r in results)
            stats = {
                "completed": total_executed,
                "total": self._total_tasks,
                "success": sum(r['success_commands'] for r in results),
                "failed": sum(r['failed_commands'] for r in results),
                "devices_updated": self._get_devices_update_info(devices)
            }
            try:
                progress_callback("configuring", 100, stats)
            except Exception:
                pass

        self._log(f"[async] 配置完成: 共{len(results)} 台设备有执行结果", "INFO")
        return results


    async def _async_execute_by_command(self, devices, mode="standard", progress_callback=None, stop_callback=None) -> dict:
        """
        异步版命令优先策略 V2 — 全并发加速

        所有设备×所有命令一次性提交到 asyncio，通过
        asyncio.Semaphore(config_concurrent) 控制总并发度。
        取代原有"命令内设备并发，命令间串行"的模式。
        """
        self._log(f"[async V2] 使用命令优先全并发策略，将对 {len(devices)} 台设备执行命令", "INFO")

        base_commands = self.config.get("cgi_commands", [])
        if not base_commands:
            self._log("没有配置CGI命令", "ERROR")
            return []

        # 只考虑在线且符合条件的设备
        online_devices = [d for d in devices if d.online and d.status in ["在线", "正在配置", "等待配置"]]
        if not online_devices:
            self._log("没有在线设备需要执行命令", "WARNING")
            return []

        self._log(f"[async V2] 在线设备数: {len(online_devices)}, 基础命令数: {len(base_commands)}", "INFO")

        # 结果初始化
        results = [{
            'device': d,
            'ip': d.ip,
            'port': d.port,
            'success': False,
            'total_commands': 0,
            'success_commands': 0,
            'failed_commands': 0,
            'failure_details': "",
            'start_time': datetime.now().strftime("%H:%M:%S"),
            'end_time': "",
            'total_time': 0
        } for d in online_devices]

        # 快速 IP → 结果索引 映射
        ip_to_idx = {d.ip: i for i, d in enumerate(online_devices)}

        # 并发控制：总并发度 = config_concurrent
        semaphore = asyncio.Semaphore(self.config_concurrent)

        # ---- 生成所有任务 (dev × cmd) ----
        all_tasks: List[asyncio.Task] = []

        for dev in online_devices:
            if not self._is_device_eligible_for_config(dev):
                continue

            for cmd_idx, base_cmd in enumerate(base_commands, 1):
                # 变量过滤 / 自定义命令生成
                if mode == "customized" and dev.variables:
                    cmd = self._generate_custom_command(base_cmd, dev.variables)
                    if not cmd:
                        continue
                else:
                    if re.search(r'\{([^}]+)\}', base_cmd):
                        continue
                    cmd = base_cmd

                async def _send_one(device, command_text, command_index):
                    # 内部检查停止标志（每任务执行前检查）
                    if self._is_stopped() or (stop_callback and stop_callback()):
                        return device, command_index, False, "已停止"

                    async with semaphore:
                        try:
                            result = await self.async_manager.send_command_async(device, command_text)
                            ok, msg = result[0], result[1]
                        except asyncio.CancelledError:
                            ok, msg = False, '已取消'
                        except Exception as e:
                            ok, msg = False, f'异步请求异常: {e}'
                        return device, command_index, ok, msg

                task = asyncio.create_task(
                    _send_one(dev, cmd, cmd_idx)
                )
                all_tasks.append(task)

        if not all_tasks:
            self._log("[async V2] 没有可执行的任务（可能所有命令都含变量且非 customized 模式）", "WARNING")
            return []

        self._log(f"[async V2] 总提交任务数: {len(all_tasks)}", "INFO")

        # ---- 一次性等待所有任务完成 ----
        completed_results = await asyncio.gather(*all_tasks, return_exceptions=True)

        # ---- 汇总结果 ----
        for completed in completed_results:
            if isinstance(completed, Exception):
                self._log(f"[async V2] 任务异常: {completed}", "ERROR")
                continue

            try:
                dev, cmd_idx, ok, msg = completed
            except (ValueError, TypeError) as e:
                self._log(f"[async V2] 结果解析异常: {e}", "ERROR")
                continue

            idx = ip_to_idx.get(dev.ip)
            if idx is None:
                continue

            results[idx]['total_commands'] += 1
            if ok:
                results[idx]['success_commands'] += 1
            else:
                results[idx]['failed_commands'] += 1
                if results[idx]['failure_details']:
                    results[idx]['failure_details'] += "; "
                results[idx]['failure_details'] += f"命令{cmd_idx}: {msg}"
                self.log_manager.log_failure(dev, f"命令执行失败: {msg}")

            # 更新全局进度
            self._completed_tasks += 1

        # ---- 进度回调（批量汇总后触发一次） ----
        if progress_callback:
            progress = (self._completed_tasks / self._total_tasks * 100) if self._total_tasks > 0 else 0
            stats = {
                'completed': self._completed_tasks,
                'total': self._total_tasks,
                'success': sum(r['success_commands'] for r in results),
                'failed': sum(r['failed_commands'] for r in results),
                'devices_updated': self._get_devices_update_info(online_devices),
            }
            try:
                progress_callback('configuring', progress, stats)
            except Exception:
                pass

        # ---- 最终化结果 ----
        end_time = datetime.now()
        for i, (res, dev) in enumerate(zip(results, online_devices)):
            res['end_time'] = end_time.strftime("%H:%M:%S")
            start_time = datetime.strptime(res['start_time'], "%H:%M:%S")
            res['total_time'] = (end_time - start_time).total_seconds()
            total_executed = res['success_commands'] + res['failed_commands']
            res['success'] = res['success_commands'] > 0 if total_executed > 0 else False
            dev.status = '成功' if res['success'] else ('部分完成' if total_executed > 0 else dev.status)
            dev.last_message = f"完成: {total_executed}/{res['total_commands']}命令" if res['total_commands'] > 0 else dev.last_message

        # ---- 最终进度 ----
        if progress_callback:
            total_executed = sum(r['success_commands'] + r['failed_commands'] for r in results)
            stats = {
                "completed": total_executed,
                "total": self._total_tasks,
                "success": sum(r['success_commands'] for r in results),
                "failed": sum(r['failed_commands'] for r in results),
                "devices_updated": self._get_devices_update_info(online_devices),
            }
            try:
                progress_callback("configuring", 100, stats)
            except Exception:
                pass

        self._log(f"[async V2] 命令优先全并发策略完成: 提交 {len(all_tasks)} 任务, {len(results)} 个设备结果", "INFO")
        return results

    # ====================== 异步实现结束 ==============================

    def _generate_custom_command(self, base_cmd, variables) -> Optional[dict]:
        """生成自定义命令"""
        custom_cmd = base_cmd
        
        # 查找命令中的所有变量占位符
        placeholders = re.findall(r'\{([^}]+)\}', base_cmd)
        
        if not placeholders:
            return base_cmd
        
        # 检查所有占位符是否都有对应的变量
        for placeholder in placeholders:
            if placeholder not in variables:
                self._log(f"跳过命令 '{base_cmd[:50]}...'，变量 '{placeholder}' 未在设备变量中找到", "DEBUG")
                return None
        
        # 所有变量都存在，进行替换
        for var_name, var_value in variables.items():
            placeholder = f"{{{var_name}}}"
            if placeholder in custom_cmd:
                custom_cmd = custom_cmd.replace(placeholder, str(var_value))
        
        return custom_cmd

    def _send_command(self, device, command, cmd_index, total_commands) -> tuple:
        """发送单个CGI命令"""
        try:
            # 发送命令前再次检查设备是否在线
            if not device.online:
                return False, "设备离线"
            
            # 构建完整的CGI请求URL
            base_url = f"http://{device.ip}:{device.port}/cgi-bin/configManager.cgi"
            encoded_cmd = requests.utils.quote(command, safe='')
            display_cmd = encoded_cmd.replace('%20', ' ')
            full_url = f"{base_url}?action=setConfig&{encoded_cmd}"
            display_url = f"{base_url}?action=setConfig&{display_cmd}"
            
            # 显示完整的CGI请求URL
            self._log(f"设备 {device.ip} CGI请求 {cmd_index}/{total_commands}: {display_url}", "INFO")
            
            if self.auth_method == "digest":
                auth = HTTPDigestAuth(device.username, device.password)
                auth_type = "Digest"
            else:
                auth = HTTPBasicAuth(device.username, device.password)
                auth_type = "Basic"
            
            self._log(f"设备 {device.ip} 使用{auth_type}认证", "DEBUG")
            
            # 记录详细的请求元数据
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Accept': '*/*',
                'Connection': 'close'
            }
            # 记录原始请求信息
            self.log_manager.log_cgi_request(
                device.ip, cmd_index, total_commands, full_url, auth_type, headers, raw_command=command
)
            self.log_manager.log_raw_request(
                device.ip, cmd_index, total_commands, full_url, command, auth_type, headers
            )
            
            # 如果启用了异步执行且有 async manager，则使用异步路径
            if self.use_async and self.async_manager:
                try:
                    # 将字符串命令转换为字典格式，兼容异步执行器
                    if isinstance(command, str):
                        # 解析字符串命令格式："VideoWidget[0].CustomTitle[1].EncodeBlend=true"
                        if '=' in command:
                            key, value = command.split('=', 1)
                            command_dict = {
                                "action": "setConfig",
                                "param": {
                                    key: value
                                }
                            }
                        else:
                            # 如果不是setConfig命令，使用默认格式
                            command_dict = {
                                "action": command
                            }
                    else:
                        # 如果已经是字典，直接使用
                        command_dict = command
                    
                    # 记录异步请求信息
                    self.log_manager.log_cgi_request(
                        device.ip, cmd_index, total_commands, full_url, auth_type, headers, raw_command=command
)
                    self.log_manager.log_raw_request(
                        device.ip, cmd_index, total_commands, full_url, command, auth_type, headers
                    )
                    
                    # 记录开始时间
                    request_start = datetime.now()
                    
                    fut = self.async_manager.send_command(device, command_dict)
                    # 等待异步结果（在同步线程中阻塞等待），超时时间稍微宽裕一些
                    result = fut.result(timeout=self.timeout + 5)
                    
                    # 解析异步执行器返回的详细信息
                    if len(result) == 5:
                        ok, message, status_code, response_headers, response_body = result
                    else:
                        # 兼容旧版本返回格式
                        ok, message = result
                        status_code = 200 if ok else "ASYNC_ERROR"
                        response_headers = {}
                        response_body = message
                    
                    # 计算响应时间
                    request_time = (datetime.now() - request_start).total_seconds()
                    
                    # 记录异步响应信息
                    if ok:
                        self.log_manager.log_cgi_response(
                            device.ip, status_code, request_time, response_headers, 
                            response_body, success=True, raw_command=command
                        )
                        self.log_manager.log_raw_response(
                            device.ip, status_code, request_time, response_headers, 
                            response_body, raw_command=command
                        )
                    else:
                        self.log_manager.log_cgi_response(
                            device.ip, status_code, request_time, response_headers, 
                            response_body, success=False, raw_command=command
                        )
                        self.log_manager.log_raw_response(
                            device.ip, status_code, request_time, response_headers, 
                            response_body, raw_command=command
                        )
                    
                    return ok, message
                except Exception as e:
                    self._log(f"异步CGI请求失败: {e}", "ERROR")
                    
                    # 计算响应时间
                    request_time = (datetime.now() - request_start).total_seconds()
                    
                    # 记录异步异常信息
                    self.log_manager.log_cgi_response(
                        device.ip, "ASYNC_EXCEPTION", request_time, {}, 
                        f"异步请求异常: {str(e)[:100]}", success=False, raw_command=command
                    )
                    self.log_manager.log_raw_response(
                        device.ip, "ASYNC_EXCEPTION", request_time, {}, 
                        f"异步请求异常: {str(e)[:100]}", raw_command=command
                    )
                    
                    return False, f"异步请求失败: {e}"
            
            request_start = datetime.now()
            
            response = self.session.get(
                full_url,
                auth=auth,
                timeout=self.timeout,
                verify=self.config.get('verify_ssl', True),
                headers=headers
            )
            
            request_time = (datetime.now() - request_start).total_seconds()
            
            # 记录详细的响应元数据
            response_headers = dict(response.headers)
            response_text = response.text.strip() if response.text else ""
            
            # 显示响应信息
            if response.status_code == 200:
                self._log(f"设备 {device.ip} CGI响应: 状态码=200, 耗时={request_time:.2f}s, 响应内容='{response_text}'", "INFO")
                
                # 记录详细的成功响应
                self.log_manager.log_cgi_response(
                    device.ip, response.status_code, request_time, 
                    response_headers, response_text, success=True, raw_command=command
                )
                self.log_manager.log_raw_response(
                    device.ip, response.status_code, request_time, 
                    response_headers, response_text, raw_command=command
                )
                
                if "OK" in response_text.upper() or response_text == "":
                    return True, "成功"
                else:
                    error_msg = f"响应内容异常: '{response_text}'"
                    self._log(f"设备 {device.ip} 命令执行失败: {error_msg}", "ERROR")
                    return False, error_msg
            else:
                error_msg = f"HTTP错误 {response.status_code}, 耗时={request_time:.2f}s"
                if response_text:
                    error_msg += f", 响应内容: '{response_text[:200]}'"
                
                self._log(f"设备 {device.ip} {error_msg}", "ERROR")
                
                # 记录详细的错误响应
                self.log_manager.log_cgi_response(
                    device.ip, response.status_code, request_time, 
                    response_headers, response_text, success=False, raw_command=command
                )
                self.log_manager.log_raw_response(
                    device.ip, response.status_code, request_time, 
                    response_headers, response_text, raw_command=command
                )
                
                if response.status_code == 401:
                    return False, f"认证失败 (401 {auth_type})"
                elif response.status_code == 400:
                    return False, f"请求错误 (400)"
                else:
                    return False, f"HTTP {response.status_code}"
                    
        except requests.exceptions.Timeout:
            error_msg = f"CGI请求超时 (超时设置: {self.timeout}s)"
            self._log(f"设备 {device.ip} {error_msg}", "ERROR")
            
            # 记录超时错误
            self.log_manager.log_cgi_response(
                device.ip, "TIMEOUT", self.timeout, {}, 
                f"请求超时 (超时设置: {self.timeout}s)", success=False, raw_command=command
            )
            self.log_manager.log_raw_response(
                device.ip, "TIMEOUT", self.timeout, {}, 
                f"请求超时 (超时设置: {self.timeout}s)", raw_command=command
            )
            
            return False, "请求超时"
            
        except requests.exceptions.ConnectionError as e:
            error_msg = f"连接失败: {e}"
            self._log(f"设备 {device.ip} {error_msg}", "ERROR")
            
            # 记录连接错误
            self.log_manager.log_cgi_response(
                device.ip, "CONNECTION_ERROR", 0, {}, 
                f"连接失败: {e}", success=False, raw_command=command
            )
            self.log_manager.log_raw_response(
                device.ip, "CONNECTION_ERROR", 0, {}, 
                f"连接失败: {e}", raw_command=command
            )
            
            return False, "连接失败"
            
        except Exception as e:
            error_msg = f"请求异常: {e}"
            self._log(f"设备 {device.ip} {error_msg}", "ERROR")
            
            # 记录其他异常
            self.log_manager.log_cgi_response(
                device.ip, "EXCEPTION", 0, {}, 
                f"请求异常: {str(e)[:100]}", success=False, raw_command=command
            )
            self.log_manager.log_raw_response(
                device.ip, "EXCEPTION", 0, {}, 
                f"请求异常: {str(e)[:100]}", raw_command=command
            )
            
            return False, f"请求异常: {str(e)[:100]}"


# ============================================================================
# 设备状态缓存 (TTL 过期 + 主动刷新)
# ============================================================================

class DeviceStatusCache:
    """
    设备状态缓存
    - 缓存每个设备的最新状态（在线/离线），带 TTL 过期
    - 支持主动刷新
    - 线程安全
    """
    
    def __init__(self, default_ttl: int = 60):
        """
        Args:
            default_ttl: 默认缓存有效期（秒），默认 60 秒
        """
        self._default_ttl = default_ttl
        self._cache: Dict[str, '_CacheEntry'] = {}
        self._lock = threading.RLock()
    
    def get(self, device_ip: str) -> Optional[Dict]:
        """获取缓存的设备状态，过期返回 None"""
        with self._lock:
            entry = self._cache.get(device_ip)
            if entry is None:
                return None
            if entry.is_expired():
                del self._cache[device_ip]
                return None
            return entry.data
    
    def set(self, device_ip: str, data: Dict, ttl: Optional[int] = None) -> None:
        """设置设备状态缓存"""
        with self._lock:
            self._cache[device_ip] = _CacheEntry(
                data=data,
                ttl=ttl if ttl is not None else self._default_ttl,
                timestamp=datetime.now()
            )
    
    def invalidate(self, device_ip: str) -> None:
        """主动失效某设备缓存"""
        with self._lock:
            self._cache.pop(device_ip, None)
    
    def invalidate_all(self) -> None:
        """主动失效全部缓存"""
        with self._lock:
            self._cache.clear()
    
    def get_all(self) -> Dict[str, Dict]:
        """获取所有有效（未过期）缓存"""
        result = {}
        with self._lock:
            expired_keys = []
            for ip, entry in self._cache.items():
                if entry.is_expired():
                    expired_keys.append(ip)
                else:
                    result[ip] = entry.data
            for k in expired_keys:
                del self._cache[k]
        return result
    
    def get_cache_info(self) -> Dict:
        """获取缓存统计信息"""
        with self._lock:
            now = datetime.now()
            valid = 0
            expired = 0
            for entry in self._cache.values():
                if entry.is_expired():
                    expired += 1
                else:
                    valid += 1
            return {
                "total": len(self._cache),
                "valid": valid,
                "expired": expired,
                "default_ttl": self._default_ttl,
            }


class _CacheEntry:
    """缓存条目，记录数据和过期时间"""
    __slots__ = ('data', 'ttl', 'timestamp')
    
    def __init__(self, data: Dict, ttl: int, timestamp: datetime):
        self.data = data
        self.ttl = ttl
        self.timestamp = timestamp
    
    def is_expired(self) -> bool:
        return (datetime.now() - self.timestamp).total_seconds() >= self.ttl


# ============================================================================
# 批量设备扫描器（并行 CGI 加速）
# ============================================================================

class DeviceScanner:
    """
    批量设备扫描器
    - 使用 concurrent.futures 对多台设备并行发起 CGI 探测请求
    - 集成 DeviceStatusCache 避免重复扫描
    - 自动记录扫描速度指标日志
    """
    
    def __init__(self, config: Dict, log_manager, log_callback=None):
        self.config = config
        self.log_manager = log_manager
        self.log_callback = log_callback
        self.max_workers = config.get("scan_concurrent", 50)
        self.scan_timeout = config.get("scan_timeout", 3.0)  # 单台超时（秒）
        self.auth_method = config.get("auth_method", "digest")
        self.session = self._create_session()
        self.cache = DeviceStatusCache(default_ttl=config.get("cache_ttl", 60))
        self._stop_flag = threading.Event()
    
    def _log(self, message: str, level: str = "INFO") -> None:
        """统一日志"""
        if self.log_callback:
            try:
                self.log_callback(message, level)
            except Exception:
                pass
        if self.log_manager:
            self.log_manager.log_detailed(message, level)
    
    @staticmethod
    def _create_session() -> requests.Session:
        """创建高性能 HTTP 会话"""
        session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=200,
            pool_maxsize=200,
            max_retries=Retry(total=1, backoff_factor=0.3, status_forcelist=[502, 503, 504])
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session
    
    def stop(self) -> None:
        """停止扫描"""
        self._stop_flag.set()
        try:
            self.session.close()
        except Exception:
            pass
    
    def _is_stopped(self) -> bool:
        return self._stop_flag.is_set()
    
    def _probe_device_cgi(self, device: DeviceInfo) -> Dict:
        """
        单独探测一台设备的 CGI 可用性
        发送简单的 status/global 请求检查设备响应
        Returns:
            dict: { "ip": ..., "online": bool, "status_code": ..., "response_time": ..., "error": str }
        """
        result = {
            "ip": device.ip,
            "online": False,
            "status_code": None,
            "response_time": 0.0,
            "error": None,
            "device": device,
        }
        
        try:
            # 优先使用 /cgi-bin/global.cgi?action=getCurrentTime 快速轻量探测
            url = f"http://{device.ip}:{device.port}/cgi-bin/global.cgi?action=getCurrentTime"
            
            if self.auth_method == "digest":
                auth = HTTPDigestAuth(device.username, device.password)
            else:
                auth = HTTPBasicAuth(device.username, device.password)
            
            start = datetime.now()
            resp = self.session.get(url, auth=auth, timeout=self.scan_timeout, verify=False)
            elapsed = (datetime.now() - start).total_seconds()
            
            result["response_time"] = round(elapsed, 3)
            result["status_code"] = resp.status_code
            
            if resp.status_code == 200:
                result["online"] = True
                result["error"] = None
            else:
                result["error"] = f"HTTP {resp.status_code}"
            
        except requests.Timeout:
            result["error"] = "timeout"
        except requests.ConnectionError:
            result["error"] = "connection_refused"
        except Exception as e:
            result["error"] = str(e)[:100]
        
        return result
    
    def scan_batch(self, devices: List[DeviceInfo], progress_callback=None) -> List[Dict]:
        """
        批量并行扫描设备
        
        - 优先使用缓存，过期或缺失的设备走实时探测
        - 实时探测使用 ThreadPoolExecutor 并行
        - 自动记录扫描指标
        
        Args:
            devices: 设备列表
            progress_callback: Optional[Callable[[int, int], None]] (completed, total)
        
        Returns:
            List[Dict]: 每台设备扫描结果
        """
        self._stop_flag.clear()
        scan_start = datetime.now()
        
        # 日志：扫描开始
        self._log(f"[Scanner] 开始批量扫描 {len(devices)} 台设备 (扫描并发={self.max_workers}, 单台超时={self.scan_timeout}s)", "INFO")
        self.log_manager.log_detailed(f"[Scanner] 批量扫描启动 | 设备数={len(devices)} | 并发={self.max_workers} | 超时={self.scan_timeout}s", "INFO")
        
        # 1. 从缓存获取有效状态
        needs_probe = []
        results = []
        cache_hits = 0
        
        for device in devices:
            cached = self.cache.get(device.ip)
            if cached is not None:
                # 缓存命中
                results.append(cached)
                cache_hits += 1
                # 同时更新设备对象的在线状态
                device.online = cached["online"]
                device.status = "在线" if cached["online"] else "离线"
            else:
                needs_probe.append(device)
        
        self._log(f"[Scanner] 缓存命中 {cache_hits}/{len(devices)}，需实时探测 {len(needs_probe)} 台", "INFO")
        
        # 2. 并行实时探测
        live_results = []
        if needs_probe and not self._is_stopped():
            live_results = self._probe_parallel(needs_probe, progress_callback)
            
            # 3. 更新缓存和设备状态
            for scan_result in live_results:
                ip = scan_result["ip"]
                # 写入缓存
                self.cache.set(ip, scan_result)
                # 更新原生 DeviceInfo 对象
                device = scan_result.get("device")
                if device:
                    device.online = scan_result["online"]
                    if scan_result["online"]:
                        device.status = "在线"
                        device.last_message = f"CGI可达 (响应时间:{scan_result['response_time']}s)"
                    else:
                        device.status = "离线"
                        device.last_message = f"CGI不可达: {scan_result['error']}"
        
        # 4. 合并结果
        all_results = results + live_results
        
        # 5. 统计指标
        scan_elapsed = (datetime.now() - scan_start).total_seconds()
        online_count = sum(1 for r in all_results if r.get("online"))
        failed_count = sum(1 for r in all_results if not r.get("online"))
        
        # 计算超时/错误分布
        timeout_count = sum(1 for r in all_results if r.get("error") == "timeout")
        refuse_count = sum(1 for r in all_results if r.get("error") == "connection_refused")
        http_err_count = sum(1 for r in all_results if r.get("error") and r["error"].startswith("HTTP"))
        other_err_count = sum(1 for r in all_results if r.get("error") and r["error"] not in ("timeout", "connection_refused") and not r["error"].startswith("HTTP"))
        
        # 日志：扫描完成
        self._log(f"[Scanner] 扫描完成 | 总耗时={scan_elapsed:.2f}s | 在线={online_count} | 离线={failed_count} | "
                  f"超时={timeout_count} | 连接拒绝={refuse_count} | HTTP错误={http_err_count} | 其他错误={other_err_count}", "INFO")
        self.log_manager.log_detailed(
            f"[Scanner] 批量扫描结果 | "
            f"设备总数={len(all_results)} | 在线={online_count} | 离线={failed_count} | "
            f"缓存命中={cache_hits} | 实时探测={len(live_results)} | "
            f"总耗时={scan_elapsed:.2f}s | 平均每台={scan_elapsed/max(len(devices),1)*1000:.1f}ms | "
            f"超时={timeout_count} | 连接拒绝={refuse_count} | HTTP错误={http_err_count} | 其他错误={other_err_count}",
            "INFO"
        )
        
        return all_results
    
    def _probe_parallel(self, devices: List[DeviceInfo], progress_callback=None) -> List[Dict]:
        """使用 ThreadPoolExecutor 并行探测设备"""
        total = len(devices)
        completed = [0]  # mutable for closure
        live_results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_map = {executor.submit(self._probe_device_cgi, d): d for d in devices}
            
            for future in concurrent.futures.as_completed(future_map):
                if self._is_stopped():
                    break
                completed[0] += 1
                try:
                    result = future.result(timeout=self.scan_timeout + 2)
                    live_results.append(result)
                except Exception as e:
                    device = future_map[future]
                    live_results.append({
                        "ip": device.ip,
                        "online": False,
                        "status_code": None,
                        "response_time": 0.0,
                        "error": f"scan_exception: {e}",
                        "device": device,
                    })
                if progress_callback:
                    try:
                        progress_callback(completed[0], total)
                    except Exception:
                        pass
        
        return live_results
    
    def refresh_one(self, device: DeviceInfo) -> Dict:
        """主动刷新单台设备状态（跳过缓存）"""
        self.cache.invalidate(device.ip)
        return self._probe_device_cgi(device)
    
    def refresh_all(self, devices: List[DeviceInfo], progress_callback=None) -> List[Dict]:
        """主动刷新全部设备状态（跳过缓存）"""
        self.cache.invalidate_all()
        self._log(f"[Scanner] 主动刷新全部 {len(devices)} 台设备状态", "INFO")
        return self._probe_parallel(devices, progress_callback)
    
    def close(self) -> None:
        """释放资源"""
        try:
            self.session.close()
        except Exception:
            pass
        self.cache.invalidate_all()
