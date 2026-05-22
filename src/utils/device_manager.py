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
    
    def get_display_info(self):
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
    
    def __init__(self, log_manager):
        self.log_manager = log_manager
        self.devices: List[DeviceInfo] = []
        self.excel_source_file = ""
        self.loaded_time = None
    
    def load_from_excel(self, file_path, mode="standard"):
        """从Excel加载设备"""
        try:
            self.log_manager.log_detailed(f"开始加载Excel文件: {file_path}", "INFO")
            print(f"加载Excel文件: {file_path}")
            
            self.excel_source_file = file_path
            self.loaded_time = datetime.now()
            
            # 读取Excel
            df = pd.read_excel(file_path, dtype=str)
            total_rows = len(df)
            
            if total_rows == 0:
                raise ValueError("Excel文件为空")
            
            print(f"读取到 {total_rows} 行数据")
            self.log_manager.log_detailed(f"Excel文件读取完成，共{total_rows}行", "INFO")
            
            self.devices.clear()
            column_mapping = self._analyze_columns(df)
            
            valid_rows = 0
            for idx, row in df.iterrows():
                device = self._parse_row(idx, row, column_mapping, mode)
                if device:
                    # 将设备index规范为在解析后列表中的顺序索引，
                    # 保证 DeviceInfo.index 与 self.devices 的下标一致，
                    # 以便UI和进度回调可以使用 device.index 安全定位主列表中的设备。
                    device.excel_row = idx + 2
                    device.index = len(self.devices)
                    self.devices.append(device)
                    valid_rows += 1
            
            self.log_manager.log_detailed(f"成功解析 {valid_rows} 台有效设备", "INFO")
            print(f"成功加载 {valid_rows} 台设备")
            
            return self.devices, valid_rows
            
        except Exception as e:
            error_msg = f"加载Excel失败: {str(e)}"
            self.log_manager.log_detailed(error_msg, "ERROR")
            print(error_msg)
            raise
    
    def _analyze_columns(self, df):
        """分析Excel列结构"""
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
    
    def _parse_row(self, idx, row, column_mapping, mode):
        """解析单行数据"""
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
            
            device = DeviceInfo(
                index=idx,
                ip=ip,
                port=port,
                username=username,
                password=password,
                status="未检测"
            )
            
            if mode == "customized" and device.variables:
                device.variables = self._extract_variables(row)
            
            return device
            
        except Exception as e:
            self.log_manager.log_detailed(f"解析第{idx+1}行失败: {e}", "WARNING")
            return None
    
    def _extract_variables(self, row):
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
    
    def __init__(self, config, log_manager, log_callback=None):
        self.config = config
        self.log_manager = log_manager
        self.log_callback = log_callback
        self.ping_concurrent = config.get("ping_concurrent", 100)
        self.ping_timeout = config.get("ping_timeout", 100)
        self.config_concurrent = config.get("config_concurrent", 5)
        self.ping_count = 1
    
    def _log(self, message, level="INFO"):
        """统一的GUI日志记录方法 - 仅用于显示处理后的进度信息"""
        # 过滤进度相关的日志
        if "进度" in message and level in ["DEBUG", "INFO"]:
            return
            
        # 调用日志回调（仅显示到GUI）
        if self.log_callback:
            try:
                self.log_callback(message, level)
            except:
                pass
        
        # 注意：这里不记录到文件，因为GUI日志应该是处理后的进度信息
    
    def detect_devices(self, devices, progress_callback=None, stop_callback=None):
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
    
    def _fast_ping(self, ip):
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
    
    def __init__(self, config, log_manager, log_callback=None, use_async=False):
        self.config = config
        self.log_manager = log_manager
        self.log_callback = log_callback
        self.config_concurrent = config.get("config_concurrent", 30)  # 进一步提高默认并发数到30
        self.timeout = config.get("timeout", 3000) / 1000.0  # 增加超时时间到3秒
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
                # AsyncIOManager 会在后台线程启动事件循环并创建 aiohttp session
                self.async_manager = AsyncIOManager(timeout=self.timeout, verify_ssl=self.config.get('verify_ssl', False), max_connections=300, auth_method=self.auth_method)  # 进一步提高连接池到300
                self._async_semaphore = asyncio.Semaphore(self.config_concurrent)  # 设备级别的共享信号量
                self._async_command_semaphore = asyncio.Semaphore(self.config_concurrent * 2)  # 命令级别的信号量，允许更多并发
                self._log(f"AsyncIOManager 已初始化，设备并发数: {self.config_concurrent}，命令并发数: {self.config_concurrent * 2}", "DEBUG")
            except Exception:
                self._log("初始化 AsyncIOManager 失败，回退到同步模式", "WARNING")
                self.async_manager = None

    def _log(self, message, level="INFO"):
        """统一的日志记录方法"""
        # 过滤进度相关的日志
        if "进度" in message and level in ["DEBUG", "INFO"]:
            return
            
        # 调用日志回调
        if self.log_callback:
            try:
                self.log_callback(message, level)
            except:
                pass
        
        # 记录到文件
        if self.log_manager:
            self.log_manager.log_detailed(message, level)

    def _create_session(self):
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

    def stop(self):
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

    def _is_stopped(self):
        """检查是否已停止"""
        return self._stop_flag.is_set()

    def _check_and_mark_device_processing(self, device):
        """检查并标记设备为处理中（线程安全）"""
        with self._device_lock:
            if device.ip in self._device_processing:
                return False  # 设备已经在处理中
            self._device_processing.add(device.ip)
            return True

    def _unmark_device_processing(self, device):
        """取消设备的处理标记（线程安全）"""
        with self._device_lock:
            if device.ip in self._device_processing:
                self._device_processing.remove(device.ip)

    def _is_device_eligible_for_config(self, device):
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

    def _configure_device_strict_wrapper(self, device, mode="standard", progress_callback=None):
        """设备配置的包装方法，确保异常时清理标记"""
        try:
            result = self._configure_device_strict(device, mode, progress_callback)
            return result
        except Exception as e:
            self._log(f"设备 {device.ip} 配置包装方法异常: {e}", "ERROR")
            # 确保清理设备标记
            self._unmark_device_processing(device)
            raise

    def _cleanup_device_processing(self):
        """清理所有设备处理标记"""
        with self._device_lock:
            self._device_processing.clear()

    def execute_batch(self, devices, mode="standard", exec_strategy="device_first", 
                     progress_callback=None, stop_callback=None, total_tasks=None):
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
                    # 暂时仍使用同步的命令优先实现以保持兼容
                    return self._execute_by_command_strict(target_devices, mode, progress_callback, stop_callback)
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

    def _execute_by_device_strict(self, devices, mode="standard", progress_callback=None, stop_callback=None):
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
    
    def _configure_device_strict(self, device, mode="standard", progress_callback=None):
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

    def _execute_by_command_strict(self, devices, mode="standard", progress_callback=None, stop_callback=None):
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

    def _get_devices_update_info(self, devices):
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
    async def _async_config_device(self, device, mode="standard", progress_callback=None, semaphore=None):
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

    async def _async_send_command_with_url_auth(self, device, command, cmd_index, total_commands):
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

    async def _async_execute_by_device(self, devices, mode="standard", progress_callback=None, stop_callback=None):
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


    async def _async_execute_by_command(self, devices, mode="standard", progress_callback=None, stop_callback=None):
        """异步版的命令优先策略实现：对每条命令并发执行到所有在线设备。"""
        self._log(f"[async] 使用命令优先策略，将对 {len(devices)} 台设备执行命令", "INFO")

        base_commands = self.config.get("cgi_commands", [])
        if not base_commands:
            self._log("没有配置CGI命令", "ERROR")
            return []

        # 只考虑在线且符合条件的设备
        online_devices = [d for d in devices if d.online and d.status in ["在线", "正在配置", "等待配置"]]
        if not online_devices:
            self._log("没有在线设备需要执行命令", "WARNING")
            return []

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

        semaphore = asyncio.Semaphore(self.config_concurrent)

        for cmd_idx, base_cmd in enumerate(base_commands, 1):
            if self._is_stopped() or (stop_callback and stop_callback()):
                self._log("配置被停止 (async 命令优先)", "WARNING")
                break

            self._log(f"[async] 执行命令 {cmd_idx}/{len(base_commands)}: {base_cmd}", "INFO")

            # 为每个设备生成命令并提交异步任务
            tasks = []
            for dev in online_devices:
                if not self._is_device_eligible_for_config(dev):
                    continue

                if mode == "customized" and dev.variables:
                    cmd = self._generate_custom_command(base_cmd, dev.variables)
                    if not cmd:
                        continue
                else:
                    if re.search(r'\{([^}]+)\}', base_cmd):
                        continue
                    cmd = base_cmd

                async def _send_with_sem(d, c):
                    async with semaphore:
                        try:
                            # AsyncIOManager.send_command_async返回5个元素的元组，我们只需要前两个
                            result = await self.async_manager.send_command_async(d, c)
                            ok, msg = result[0], result[1]
                        except asyncio.CancelledError:
                            ok, msg = False, '已取消'
                        except Exception as e:
                            ok, msg = False, f'异步请求异常: {e}'
                        return d, ok, msg

                tasks.append(asyncio.create_task(_send_with_sem(dev, cmd)))

            if not tasks:
                continue

            done, pending = await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)

            for t in done:
                try:
                    dev, ok, msg = t.result()
                except Exception as e:
                    self._log(f"异步命令执行异常: {e}", "ERROR")
                    continue

                idx = online_devices.index(dev)
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

            # progress callback
            if progress_callback:
                progress = (self._completed_tasks / self._total_tasks * 100) if self._total_tasks > 0 else 0
                stats = {
                    'completed': self._completed_tasks,
                    'total': self._total_tasks,
                    'success': sum(r['success_commands'] for r in results),
                    'failed': sum(r['failed_commands'] for r in results),
                    'devices_updated': self._get_devices_update_info(online_devices)
                }
                try:
                    progress_callback('configuring', progress, stats)
                except Exception:
                    pass

        # finalize results
        end_time = datetime.now()
        for i, (res, dev) in enumerate(zip(results, online_devices)):
            res['end_time'] = end_time.strftime("%H:%M:%S")
            start_time = datetime.strptime(res['start_time'], "%H:%M:%S")
            res['total_time'] = (end_time - start_time).total_seconds()
            total_executed = res['success_commands'] + res['failed_commands']
            res['success'] = res['success_commands'] > 0 if total_executed>0 else False
            dev.status = '成功' if res['success'] else ('部分完成' if total_executed>0 else dev.status)
            dev.last_message = f"完成: {total_executed}/{res['total_commands']}命令" if res['total_commands']>0 else dev.last_message

        # final progress
        if progress_callback:
            total_executed = sum(r['success_commands'] + r['failed_commands'] for r in results)
            stats = {
                "completed": total_executed,
                "total": self._total_tasks,
                "success": sum(r['success_commands'] for r in results),
                "failed": sum(r['failed_commands'] for r in results),
                "devices_updated": self._get_devices_update_info(online_devices)
            }
            try:
                progress_callback("configuring", 100, stats)
            except Exception:
                pass

        self._log(f"[async] 命令优先策略完成: 共{len(results)} 个结果", "INFO")
        return results

    # ====================== 异步实现结束 ==============================

    def _generate_custom_command(self, base_cmd, variables):
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

    def _send_command(self, device, command, cmd_index, total_commands):
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
                verify=False,
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


async def _async_config_device(self, device, mode="standard", progress_callback=None, semaphore=None):
    """异步配置单个设备"""
    if semaphore is None:
        # 使用共享的信号量，避免每个任务都创建新的
        semaphore = self._async_semaphore
        
    start_time = datetime.now()
    success_count = 0
    failed_count = 0
    failure_details = []
    
    try:
        # 获取基础命令列表
        base_commands = self.config.get("cgi_commands", [])
        if not base_commands:
            self._log(f"设备 {device.ip} 没有配置CGI命令", "ERROR")
            return None
        
        total_commands = len(base_commands)
        self._total_tasks = total_commands * len([d for d in self.device_list if d.online])
        
        # 使用设备级别的信号量控制设备并发
        async with semaphore:
            for i, base_cmd in enumerate(base_commands, 1):
                if self._is_stopped():
                    break
                    
                # 生成实际执行的命令
                if mode == "customized" and device.variables:
                    command = self._generate_custom_command(base_cmd, device.variables)
                    if not command:
                        failed_count += 1
                        failure_details.append(f"命令{i}: 自定义命令生成失败")
                        continue
                else:
                    command = base_cmd
                
                device.last_message = f"执行第{i}/{total_commands}条命令"
        
                # 使用命令级别的信号量控制命令并发
                async with self._async_command_semaphore:
                    try:
                        # 构建完整的CGI请求URL（与同步路径保持一致）
                        base_url = f"http://{device.ip}:{device.port}/cgi-bin/configManager.cgi"
                        encoded_cmd = requests.utils.quote(command, safe='')
                        display_cmd = encoded_cmd.replace('%20', ' ')
                        full_url = f"{base_url}?action=setConfig&{encoded_cmd}"
                        display_url = f"{base_url}?action=setConfig&{display_cmd}"
                        
                        # 认证信息
                        auth_type = "Digest" if self.auth_method == "digest" else "Basic"
                        
                        # 请求头信息
                        headers = {
                            'User-Agent': 'Mozilla/5.0',
                            'Accept': '*/*',
                            'Connection': 'close'
                        }
                        
                        # 记录请求信息（与同步路径保持一致）
                        self.log_manager.log_cgi_request(
                            device.ip, i, total_commands, full_url, auth_type, headers, raw_command=command
                        )
                        self.log_manager.log_raw_request(
                            device.ip, i, total_commands, full_url, command, auth_type, headers
                        )
                        
                        # 记录开始时间
                        request_start = datetime.now()
                        
                        # 直接调用 AsyncIOManager 的内部异步发送方法
                        ok, message = await self.async_manager._send_command_async(device, command)
                        
                        # 计算响应时间
                        request_time = (datetime.now() - request_start).total_seconds()
                        
                        # 解析响应结果（模拟同步路径的五元组格式）
                        if ok:
                            status_code = 200
                            response_headers = {}  # 异步路径暂时没有响应头信息
                            response_body = message if message else "OK"
                        else:
                            status_code = "ASYNC_ERROR"
                            response_headers = {}
                            response_body = message
                        
                        # 记录响应信息（与同步路径保持一致）
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
                            
                    except asyncio.CancelledError:
                        ok, message = False, '已取消'
                        # 记录取消异常
                        request_time = (datetime.now() - request_start).total_seconds()
                        self.log_manager.log_cgi_response(
                            device.ip, "CANCELLED", request_time, {}, 
                            "请求被取消", success=False, raw_command=command
                        )
                        self.log_manager.log_raw_response(
                            device.ip, "CANCELLED", request_time, {}, 
                            "请求被取消", raw_command=command
                        )
                    except Exception as e:
                        ok, message = False, f'异步请求异常: {e}'
                        # 记录异常信息
                        request_time = (datetime.now() - request_start).total_seconds()
                        self.log_manager.log_cgi_response(
                            device.ip, "ASYNC_EXCEPTION", request_time, {}, 
                            f"异步请求异常: {str(e)[:100]}", success=False, raw_command=command
                        )
                        self.log_manager.log_raw_response(
                            device.ip, "ASYNC_EXCEPTION", request_time, {}, 
                            f"异步请求异常: {str(e)[:100]}", raw_command=command
                        )

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

        # finalize device state
        completed_count = success_count + failed_count
        if self._is_stopped():
            device.status = "已停止"
            device.last_message = f"已停止，完成 {completed_count}/{total_commands}条命令"
        elif not device.online:
            device.status = "离线"
            device.last_message = f"执行过程中离线，完成 {completed_count}/{total_commands}条命令"
        elif completed_count == total_commands:
            device.status = "成功" if success_count>0 else "失败"
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