#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 复制自 V9.4.1/utils/log_manager.py

import os
import sys
from datetime import datetime
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
import platform
import subprocess

class LogManager:
    def __init__(self):
        self.app_dir = self.get_app_directory()
        self.log_dir = os.path.join(self.app_dir, "logs")
        self.detailed_log_file = None
        self.failure_log_file = None
        self.excel_result_file = None
        self.setup_logs()

    def get_app_directory(self):
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        else:
            return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def setup_logs(self):
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.detailed_log_file = os.path.join(self.log_dir, f"detailed_{timestamp}.log")
        with open(self.detailed_log_file, 'w', encoding='utf-8') as f:
            f.write("日志初始化\n")
        self.failure_log_file = os.path.join(self.log_dir, f"failures_{timestamp}.log")
        with open(self.failure_log_file, 'w', encoding='utf-8') as f:
            f.write("失败日志\n")
        self.excel_result_file = os.path.join(self.log_dir, f"results_{timestamp}.xlsx")

    def log_detailed(self, message, level="INFO"):
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.detailed_log_file, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] [{level}] {message}\n")
        except Exception:
            pass

    def log_cgi_request(self, device_ip, command_index, total_commands, full_url, auth_type, headers, method="GET", raw_command=""):
        """记录详细的CGI请求元数据，包含原始命令"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"""[{timestamp}] [CGI_REQUEST] 设备 {device_ip} 请求 {command_index}/{total_commands}
  请求URL: {full_url}
  原始命令: {raw_command}
  请求方法: {method}
  认证方式: {auth_type}
  请求头: {headers}
"""
            with open(self.detailed_log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except Exception:
            pass

    def log_cgi_response(self, device_ip, status_code, response_time, response_headers, response_body, success=True, raw_command=""):
        """记录详细的CGI响应元数据，包含原始命令"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            status_level = "SUCCESS" if success else "ERROR"
            # 记录完整的响应内容，不截断
            response_content = response_body if response_body else '空'
            log_entry = f"""[{timestamp}] [CGI_RESPONSE] 设备 {device_ip} 响应
  原始命令: {raw_command}
  状态码: {status_code}
  响应时间: {response_time:.2f}s
  响应头: {response_headers}
  响应内容: {response_content}
"""
            with open(self.detailed_log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except Exception:
            pass

    def log_raw_request(self, device_ip, command_index, total_commands, full_url, raw_command, auth_type, headers, method="GET"):
        """记录原始请求数据，包含完整的URL和命令"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"""[{timestamp}] [RAW_REQUEST] 设备 {device_ip} 原始请求 {command_index}/{total_commands}
  完整URL: {full_url}
  原始命令: {raw_command}
  认证方式: {auth_type}
  请求头: {headers}
"""
            with open(self.detailed_log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except Exception:
            pass

    def log_raw_response(self, device_ip, status_code, response_time, response_headers, response_body, raw_command=""):
        """记录原始响应数据，包含完整的响应内容"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"""[{timestamp}] [RAW_RESPONSE] 设备 {device_ip} 原始响应
  原始命令: {raw_command}
  状态码: {status_code}
  响应时间: {response_time:.2f}s
  响应头: {response_headers}
  完整响应内容: {response_body if response_body else '空'}
"""
            with open(self.detailed_log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except Exception:
            pass

    def log_failure(self, device_info, error_message, command=""):
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.failure_log_file, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] 设备 {getattr(device_info, 'ip', '')} 失败: {error_message}\n")
        except Exception:
            pass

    def export_excel_results(self, devices, excel_source_file):
        try:
            wb = Workbook()
            ws = wb.active
            ws.title = "配置结果"
            headers = ["序号", "IP地址", "端口", "用户名", "设备状态", "配置状态"]
            for col_idx, header in enumerate(headers, 1):
                ws.cell(row=1, column=col_idx, value=header)
            for row_idx, device in enumerate(devices, 2):
                ws.cell(row=row_idx, column=1, value=row_idx-1)
                ws.cell(row=row_idx, column=2, value=device.ip)
            wb.save(self.excel_result_file)
            return self.excel_result_file
        except Exception:
            return None

    def open_failure_logs(self):
        """打开失败日志文件"""
        try:
            if os.path.exists(self.failure_log_file):
                if platform.system() == "Windows":
                    os.startfile(self.failure_log_file)
                elif platform.system() == "Darwin":
                    subprocess.run(["open", self.failure_log_file])
                else:
                    subprocess.run(["xdg-open", self.failure_log_file])
                return True
            else:
                return False
        except Exception:
            return False

    def open_log_directory(self):
        """打开日志目录"""
        try:
            if os.path.exists(self.log_dir):
                if platform.system() == "Windows":
                    os.startfile(self.log_dir)
                elif platform.system() == "Darwin":
                    subprocess.run(["open", self.log_dir])
                else:
                    subprocess.run(["xdg-open", self.log_dir])
                return True
            else:
                return False
        except Exception:
            return False