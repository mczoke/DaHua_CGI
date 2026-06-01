#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# V9.5 - 日志级别控制 + 文件轮转(100MB+5备份) + 响应截断

import logging
import os
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, List, Optional, Union

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
import platform
import subprocess


class LogManager:
    """日志管理器 — 支持级别控制、文件轮转、响应截断"""

    MAX_RESPONSE_BYTES: int = 1024  # log_raw_response 截断阈值

    def __init__(self, log_level: str = "INFO"):
        self.app_dir: str = self.get_app_directory()
        self.log_dir: str = os.path.join(self.app_dir, "logs")
        self._logger: Optional[logging.Logger] = None
        self._setup_logging(log_level)

        self.detailed_log_file: Optional[str] = None
        self.failure_log_file: Optional[str] = None
        self.excel_result_file: Optional[str] = None
        self.setup_logs()

    def _setup_logging(self, log_level: str) -> None:
        """初始化 Python logging 系统（日志级别 + 轮转）"""
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir, exist_ok=True)
        level = getattr(logging, log_level.upper(), logging.INFO)
        # 主日志文件带时间戳，但用 RotatingFileHandler 防无限增长
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        main_log = os.path.join(self.log_dir, f"app_{ts}.log")
        handler = RotatingFileHandler(
            main_log,
            maxBytes=100 * 1024 * 1024,  # 100 MB
            backupCount=5,
            encoding="utf-8",
        )
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        handler.setLevel(level)

        # 避免重复添加 handler
        root = logging.getLogger()
        # 移除其他 handler（防止多次 setup_logs 时重复）
        for h in root.handlers[:]:
            root.removeHandler(h)
        root.addHandler(handler)
        root.setLevel(level)
        self._logger = root

    def get_app_directory(self) -> str:
        if getattr(sys, "frozen", False):
            return os.path.dirname(sys.executable)
        else:
            return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def setup_logs(self) -> None:
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.detailed_log_file = os.path.join(self.log_dir, f"detailed_{timestamp}.log")
        with open(self.detailed_log_file, "w", encoding="utf-8") as f:
            f.write("日志初始化\n")
        self.failure_log_file = os.path.join(self.log_dir, f"failures_{timestamp}.log")
        with open(self.failure_log_file, "w", encoding="utf-8") as f:
            f.write("失败日志\n")
        self.excel_result_file = os.path.join(self.log_dir, f"results_{timestamp}.xlsx")

    # ---------- 统一日志记录 ----------

    def log_detailed(self, message: str, level: str = "INFO") -> None:
        """写入详细日志文件 + Python logging"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            line = f"[{timestamp}] [{level}] {message}\n"
            with open(self.detailed_log_file, "a", encoding="utf-8") as f:
                f.write(line)
            # 同步到 Python logging
            py_level = getattr(logging, level.upper(), logging.INFO)
            self._logger.log(py_level, message)
        except Exception as e:
            self._logger.error(f"log_detailed 写入失败: {e}")

    def log_failure(
        self,
        device_info: Union[object, str],
        error_message: str,
        command: str = "",
    ) -> None:
        """记录失败到失败日志"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ip = getattr(device_info, "ip", "") if not isinstance(device_info, str) else device_info
            line = f"[{timestamp}] 设备 {ip} 失败: {error_message}\n"
            with open(self.failure_log_file, "a", encoding="utf-8") as f:
                f.write(line)
            self._logger.warning(f"设备 {ip} 失败: {error_message}")
        except Exception as e:
            self._logger.error(f"log_failure 写入失败: {e}")

    # ---------- CGI 元数据日志 ----------

    def log_cgi_request(
        self,
        device_ip: str,
        command_index: int,
        total_commands: int,
        full_url: str,
        auth_type: str,
        headers: Dict[str, str],
        method: str = "GET",
        raw_command: str = "",
    ) -> None:
        """记录详细的 CGI 请求元数据"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            header_str = str(headers) if len(str(headers)) < 2048 else str(headers)[:2048] + "…(截断)"
            log_entry = (
                f"[{timestamp}] [CGI_REQUEST] 设备 {device_ip} 请求 {command_index}/{total_commands}\n"
                f"  请求URL: {full_url}\n"
                f"  原始命令: {raw_command}\n"
                f"  请求方法: {method}\n"
                f"  认证方式: {auth_type}\n"
                f"  请求头: {header_str}\n"
            )
            with open(self.detailed_log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
            self._logger.info(
                f"[CGI_REQUEST] {device_ip} {command_index}/{total_commands} {auth_type}"
            )
        except Exception as e:
            self._logger.error(f"log_cgi_request 写入失败: {e}")

    def log_cgi_response(
        self,
        device_ip: str,
        status_code: Union[int, str],
        response_time: float,
        response_headers: Dict[str, str],
        response_body: str,
        success: bool = True,
        raw_command: str = "",
    ) -> None:
        """记录详细的 CGI 响应元数据"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            status_level = "SUCCESS" if success else "ERROR"
            body = response_body if response_body else "空"
            # 截断响应 > 1KB
            if len(body) > self.MAX_RESPONSE_BYTES:
                body = body[: self.MAX_RESPONSE_BYTES] + "…(截断)"
            header_str = str(response_headers) if len(str(response_headers)) < 2048 else str(response_headers)[:2048] + "…(截断)"
            log_entry = (
                f"[{timestamp}] [{status_level}] [CGI_RESPONSE] 设备 {device_ip} 响应\n"
                f"  原始命令: {raw_command}\n"
                f"  状态码: {status_code}\n"
                f"  响应时间: {response_time:.2f}s\n"
                f"  响应头: {header_str}\n"
                f"  响应内容: {body}\n"
            )
            with open(self.detailed_log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as e:
            self._logger.error(f"log_cgi_response 写入失败: {e}")

    def log_raw_request(
        self,
        device_ip: str,
        command_index: int,
        total_commands: int,
        full_url: str,
        raw_command: str,
        auth_type: str,
        headers: Dict[str, str],
        method: str = "GET",
    ) -> None:
        """记录原始请求数据"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            header_str = str(headers) if len(str(headers)) < 2048 else str(headers)[:2048] + "…(截断)"
            log_entry = (
                f"[{timestamp}] [RAW_REQUEST] 设备 {device_ip} 原始请求 {command_index}/{total_commands}\n"
                f"  完整URL: {full_url}\n"
                f"  原始命令: {raw_command}\n"
                f"  认证方式: {auth_type}\n"
                f"  请求头: {header_str}\n"
            )
            with open(self.detailed_log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
            self._logger.debug(f"[RAW_REQUEST] {device_ip} {command_index}/{total_commands}")
        except Exception as e:
            self._logger.error(f"log_raw_request 写入失败: {e}")

    def log_raw_response(
        self,
        device_ip: str,
        status_code: Union[int, str],
        response_time: float,
        response_headers: Dict[str, str],
        response_body: str,
        raw_command: str = "",
    ) -> None:
        """记录原始响应数据 — 超过 1KB 自动截断"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            body = response_body if response_body else "空"
            need_trunc = len(body) > self.MAX_RESPONSE_BYTES
            if need_trunc:
                body = body[: self.MAX_RESPONSE_BYTES] + "…(截断)"
            header_str = str(response_headers) if len(str(response_headers)) < 2048 else str(response_headers)[:2048] + "…(截断)"
            trunc_tag = " (截断)" if need_trunc else ""
            log_entry = (
                f"[{timestamp}] [RAW_RESPONSE] 设备 {device_ip} 原始响应{trunc_tag}\n"
                f"  原始命令: {raw_command}\n"
                f"  状态码: {status_code}\n"
                f"  响应时间: {response_time:.2f}s\n"
                f"  响应头: {header_str}\n"
                f"  完整响应内容: {body}\n"
            )
            with open(self.detailed_log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
            msg = f"[RAW_RESPONSE] {device_ip} {status_code} {response_time:.2f}s"
            if need_trunc:
                msg += f" (响应 {len(response_body)}B → {self.MAX_RESPONSE_BYTES}B 截断)"
            self._logger.debug(msg)
        except Exception as e:
            self._logger.error(f"log_raw_response 写入失败: {e}")

    # ---------- Excel 导出 ----------

    def export_excel_results(
        self, devices: List[Any], excel_source_file: str
    ) -> Optional[str]:
        try:
            wb = Workbook()
            ws = wb.active
            ws.title = "配置结果"
            headers = ["序号", "IP地址", "端口", "用户名", "设备状态", "配置状态"]
            for col_idx, header in enumerate(headers, 1):
                ws.cell(row=1, column=col_idx, value=header)
            for row_idx, device in enumerate(devices, 2):
                ws.cell(row=row_idx, column=1, value=row_idx - 1)
                ws.cell(row=row_idx, column=2, value=device.ip)
            wb.save(self.excel_result_file)
            return self.excel_result_file
        except Exception as e:
            self._logger.error(f"export_excel_results 失败: {e}")
            return None

    # ---------- 日志文件快捷操作 ----------

    def open_failure_logs(self) -> bool:
        try:
            if os.path.exists(self.failure_log_file):
                self._open_file(self.failure_log_file)
                return True
            return False
        except Exception:
            return False

    def open_log_directory(self) -> bool:
        try:
            if os.path.exists(self.log_dir):
                self._open_file(self.log_dir)
                return True
            return False
        except Exception:
            return False

    @staticmethod
    def _open_file(path: str) -> None:
        """平台无关的文件/目录打开"""
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])
