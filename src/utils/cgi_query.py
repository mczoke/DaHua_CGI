#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CGI查询执行器 - V1.0
对设备批量发送 getConfig CGI 查询并收集结果，
只查询不修改设备配置。
"""

import os
import re
import json
import re
import threading
import concurrent.futures
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Callable, Union

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
from urllib.parse import parse_qs, urlparse

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class CgiQueryExecutor:
    """
    查询执行器，对设备批量发送 getConfig CGI 查询并收集结果。
    只读不写，独立于 ConfigExecutor。
    """

    def __init__(self, config, log_manager, log_callback=None):
        """
        初始化 CgiQueryExecutor

        Args:
            config: 配置字典（timeout, verify_ssl, auth_method 等）
            log_manager: LogManager 实例
            log_callback: 界面日志回调函数（可选）
        """
        self.config = config
        self.log_manager = log_manager
        self.log_callback = log_callback

        self.timeout = config.get("timeout", 3000) / 1000.0
        self.verify_ssl = config.get("verify_ssl", True)
        self.auth_method = config.get("auth_method", "digest")
        self.query_concurrent = config.get("config_concurrent", 30)

        self.session = self._create_session()
        self._stop_flag = threading.Event()

    def stop(self) -> None:
        """请求停止查询，并关闭会话以尽快中断后续请求。"""
        self._stop_flag.set()
        try:
            self.session.close()
        except Exception:
            pass

    def is_stopped(self) -> bool:
        """返回当前查询是否已收到停止请求。"""
        return self._stop_flag.is_set()

    def _create_session(self) -> requests.Session:
        """创建带重试的 requests Session"""
        session = requests.Session()
        retry_strategy = Retry(
            total=1,
            backoff_factor=0.1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=100, pool_maxsize=100)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.verify = self.verify_ssl
        return session

    def _log(self, message: str, level: str = "INFO") -> None:
        """统一的日志输出"""
        if self.log_callback:
            try:
                self.log_callback(message, level)
            except Exception:
                pass
        if self.log_manager:
            self.log_manager.log_detailed(message, level)

    def _get_auth(self, username: str, password: str):
        """根据配置的认证方式返回 auth 对象"""
        if self.auth_method == "basic":
            return HTTPBasicAuth(username, password)
        else:
            return HTTPDigestAuth(username, password)

    def _command_display_name(self, command: str) -> str:
        """返回查询结果表中使用的简洁命令列名。"""
        if command.startswith("http://") or command.startswith("https://"):
            try:
                query = parse_qs(urlparse(command).query)
                if query.get("name"):
                    return query["name"][0]
            except Exception:
                pass
        if "name=" in command:
            return command.split("name=", 1)[-1].split("&", 1)[0]
        return command.split("=")[-1] if "=" in command else command

    def _ping_device(self, ip: str) -> str:
        """Ping检测设备连通性，返回 '在线' 或 '离线'"""
        import platform
        import subprocess

        try:
            param = "-n" if platform.system().lower() == "windows" else "-c"
            timeout_param = "-w" if platform.system().lower() == "windows" else "-W"
            ping_timeout = max(int(self.config.get("ping_timeout", 2000)) / 1000, 1)

            cmd = ["ping", param, "1", timeout_param, str(int(ping_timeout)), ip]
            process = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                timeout=ping_timeout + 1,
            )
            output = process.stdout.decode(
                "gbk" if platform.system().lower() == "windows" else "utf-8",
                errors="ignore",
            ).lower()

            success_keywords = ["bytes=", "ttl=", "reply from", "来自", "time="]
            if process.returncode == 0 or any(kw in output for kw in success_keywords):
                return "在线"
            return "离线"
        except Exception:
            return "离线"

    def _verify_account(self, ip: str, port: str, username: str, password: str) -> str:
        """
        验证设备账号密码
        尝试用一个简单的CGI请求（如获取设备信息）来验证。
        返回: '通过', '失败', '未验证'
        """
        try:
            url = f"http://{ip}:{port}/cgi-bin/configManager.cgi?action=getConfig&name=General"
            auth = self._get_auth(username, password)
            resp = self.session.get(
                url,
                auth=auth,
                timeout=self.timeout,
                verify=self.verify_ssl,
            )

            if resp.status_code == 200:
                # 检查响应内容是否包含错误信息
                body = resp.text.lower()
                if "error" in body and ("401" in body or "403" in body):
                    return "失败"
                return "通过"
            elif resp.status_code in (401, 403):
                return "失败"
            else:
                return "失败"
        except requests.exceptions.ConnectTimeout:
            return "未验证"
        except requests.exceptions.ConnectionError:
            return "未验证"
        except Exception:
            return "未验证"

    def _send_query_command(
        self, ip: str, port: str, username: str, password: str, command: str
    ) -> str:
        """
        对设备发送单条 getConfig CGI 查询命令

        支持两种模式：
        1. 纯命令名模式 — 自动拼接标准CGI URL
           http://{ip}:{port}/cgi-bin/configManager.cgi?action=getConfig&name={command}
        2. 自定义URL模式 — 直接使用命令内容，支持 {{IP}} {{port}} {{username}} {{password}} 变量替换

        返回处理后的结果文本（XML/JSON提取关键内容，否则取前200字符）
        """
        # 判断是否为自定义URL模式
        if command.startswith("http://") or command.startswith("https://"):
            # 变量替换
            url = command.replace("{{IP}}", ip) \
                         .replace("{{port}}", port) \
                         .replace("{{username}}", username) \
                         .replace("{{password}}", password)
        else:
            # 纯命令名模式
            url = f"http://{ip}:{port}/cgi-bin/configManager.cgi?action=getConfig&name={command}"

        try:
            auth = self._get_auth(username, password)
            resp = self.session.get(
                url,
                auth=auth,
                timeout=self.timeout,
                verify=self.verify_ssl,
            )

            if resp.status_code != 200:
                return {"text": "", "parsed": {}}

            text = resp.text.strip()
            if not text:
                return {"text": "(空响应)", "parsed": {}}

            # 尝试解析 XML
            if text.startswith("<?xml") or text.startswith("<"):
                try:
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(text)
                    texts = []
                    for elem in root.iter():
                        if elem.text and elem.text.strip():
                            texts.append(f"{elem.tag}: {elem.text.strip()}")
                    if texts:
                        return {"text": "; ".join(texts), "parsed": {}}
                except Exception:
                    pass

            # 尝试解析 JSON
            if text.startswith("{") or text.startswith("["):
                try:
                    parsed = json.loads(text)
                    return {"text": json.dumps(parsed, ensure_ascii=False, indent=2), "parsed": {}}
                except Exception:
                    pass

            # 识别 key=value 格式（支持单行和多行，如 table.xxx=yyy）
            parsed_dict = {}
            lines = text.split("\n")
            non_empty_lines = [line.strip() for line in lines if line.strip()]
            if non_empty_lines and all("=" in line for line in non_empty_lines):
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    if "=" in line:
                        key, _, val = line.partition("=")
                        # 去掉 table.xxx 前缀，只取最后一部分作为列名
                        simple_key = key.rsplit(".", 1)[-1] if "." in key else key
                        parsed_dict[simple_key.strip()] = val.strip()
                return {"text": "", "parsed": parsed_dict}

            # 普通文本，返回完整内容
            return {"text": text, "parsed": {}}

        except requests.exceptions.ConnectTimeout:
            return {"text": "超时", "parsed": {}}
        except requests.exceptions.ConnectionError:
            return {"text": "连接失败", "parsed": {}}
        except Exception as e:
            return {"text": f"错误: {str(e)}", "parsed": {}}

    def execute_query(
        self,
        devices: List,
        query_commands: List[str],
        progress_callback: Optional[Callable] = None,
        stop_callback: Optional[Callable] = None,
        row_callback: Optional[Callable] = None,
    ) -> pd.DataFrame:
        """
        批量执行CGI查询，返回结果DataFrame

        Args:
            devices: DeviceInfo 列表
            query_commands: CGI查询命令列表（如 ["Alarm", "VideoInMode"]）
            progress_callback: 进度回调函数(progress: float)
            stop_callback: 停止回调函数，返回True时停止

        Returns:
            pd.DataFrame: 包含基础信息和查询结果的表格
        """
        self._stop_flag.clear()

        # 基础列
        base_columns = ["IP", "端口", "用户名", "密码", "Ping状态", "账号验证"]

        # 查询结果列名
        query_column_names = []
        for cmd in query_commands:
            # 简写命令名
            col_name = self._command_display_name(cmd)
            if len(col_name) > 40:
                col_name = col_name[:40]
            # 避免重复列名
            base = col_name
            suffix = 1
            while col_name in query_column_names or col_name in base_columns:
                col_name = f"{base}_{suffix}"
                suffix += 1
            query_column_names.append(col_name)

        # 列集合（基础列 + 命令列 + 展开列，动态构建）
        all_columns_set = set(base_columns)
        _seen_command_cols = base_columns.copy()

        # 准备结果列表
        results = []
        total = len(devices)

        for idx, device in enumerate(devices):
            # 检查停止回调
            if stop_callback and stop_callback():
                self._log(f"查询被用户中断 (设备 {idx+1}/{total})", "WARNING")
                break
            if self._stop_flag.is_set():
                break

            # 1. Ping检测
            ping_status = self._ping_device(device.ip)

            # 2. 账号验证
            account_status = self._verify_account(
                device.ip, device.port, device.username, device.password
            )

            # 基础信息行
            row_data = {
                "IP": device.ip,
                "端口": device.port,
                "用户名": device.username,
                "密码": device.password,
                "Ping状态": ping_status,
                "账号验证": account_status,
            }

            # 3. 逐条发送查询命令
            for cmd, col_name in zip(query_commands, query_column_names):
                if self._stop_flag.is_set() or (stop_callback and stop_callback()):
                    self._log(f"查询被用户中断 (设备 {idx+1}/{total})", "WARNING")
                    break
                result = self._send_query_command(
                    device.ip, device.port, device.username, device.password, cmd
                )
                parsed = result.get("parsed") or {}
                row_data[col_name] = next(iter(parsed.values()), "") if len(parsed) == 1 else result.get("text", "")
                if col_name not in all_columns_set:
                    all_columns_set.add(col_name)
                    _seen_command_cols.append(col_name)
                # 展开解析后的 key=value 到列（带命令名前缀）
                if parsed:
                    for k, v in parsed.items():
                        expanded_col = f"{col_name}.{k}"
                        row_data[expanded_col] = v
                        if expanded_col not in all_columns_set:
                            all_columns_set.add(expanded_col)
                            _seen_command_cols.append(expanded_col)

            results.append(row_data)
            if row_callback:
                row_callback(row_data, list(_seen_command_cols))

            # 更新进度
            if progress_callback:
                progress = ((idx + 1) / total) * 100
                progress_callback(progress)

        # 组装 DataFrame（用 _seen_command_cols 保持列顺序）
        final_columns = _seen_command_cols
        df = pd.DataFrame(results, columns=final_columns)
        # 用 NaN 填充缺失列
        for col in final_columns:
            if col not in df.columns:
                df[col] = ""
        return df[final_columns]

    def export_to_excel(self, df: pd.DataFrame, filename: str) -> str:
        """
        将查询结果DataFrame导出为格式化的Excel文件

        Args:
            df: 查询结果DataFrame
            filename: 导出文件路径

        Returns:
            str: 实际导出的文件路径
        """
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

            wb = Workbook()
            ws = wb.active
            ws.title = "CGI查询结果"

            # 表头样式
            header_font = Font(bold=True, color="FFFFFF", size=11)
            header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
            header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

            thin_border = Border(
                left=Side(style="thin"),
                right=Side(style="thin"),
                top=Side(style="thin"),
                bottom=Side(style="thin"),
            )

            # 写入表头
            columns = list(df.columns)
            for col_idx, col_name in enumerate(columns, 1):
                cell = ws.cell(row=1, column=col_idx, value=col_name)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_alignment
                cell.border = thin_border

            # 写入数据
            normal_font = Font(size=10)
            center_align = Alignment(horizontal="center", vertical="center")
            left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)

            # 定义基础列索引（用于居中对齐）
            base_cols = {"IP", "端口", "用户名", "密码", "Ping状态", "账号验证"}

            for row_idx, (_, row) in enumerate(df.iterrows(), 2):
                for col_idx, col_name in enumerate(columns, 1):
                    value = row[col_name]
                    cell = ws.cell(row=row_idx, column=col_idx, value=str(value) if pd.notna(value) else "")
                    cell.font = normal_font
                    cell.border = thin_border

                    if col_name in base_cols:
                        cell.alignment = center_align
                    else:
                        cell.alignment = left_align

            # 设置列宽
            for col_idx, col_name in enumerate(columns, 1):
                if col_name in base_cols:
                    ws.column_dimensions[chr(64 + col_idx) if col_idx <= 26 else "A"].width = 16
                else:
                    # 查询结果列宽设大一些
                    col_letter = ws.cell(row=1, column=col_idx).column_letter
                    ws.column_dimensions[col_letter].width = 40

            # 冻结首行
            ws.freeze_panes = "A2"

            # 自动筛选
            ws.auto_filter.ref = ws.dimensions

            wb.save(filename)
            return filename

        except ImportError:
            # 没有 openpyxl，fallback 到 CSV
            csv_path = os.path.splitext(filename)[0] + ".csv"
            df.to_csv(csv_path, index=False, encoding="utf-8-sig")
            return csv_path
        except Exception as e:
            raise RuntimeError(f"导出Excel失败: {e}")
