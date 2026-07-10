#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V9.6-alpha - 完整主界面 + 聚合报表
提供：
- 从 Excel 加载设备
- Ping 检测
- 编辑 CGI 命令与参数
- 启动/停止配置（使用 `ConfigExecutor(use_async=True)`）
- 聚合报表 Tab + 导出报表（CSV/Excel）
"""

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from datetime import datetime
import time
import json

import pandas as pd

from utils.config_manager import ConfigManager
from utils.log_manager import LogManager
from utils.device_manager import DeviceLoader, DeviceDetector, ConfigExecutor, DeviceInfo
from utils.aggregate_collector import AggregateResultCollector, AggregateReport
from utils.cgi_query import CgiQueryExecutor


class DeviceTableFrame(ttk.Frame):
    """设备表格（与 V9.4.x 保持兼容的最小实现）"""
    def __init__(self, parent, log_callback=None):
        super().__init__(parent)
        self.devices = []
        self.checkbox_vars = {}
        self._item_by_index = {}
        self.log_callback = log_callback
        self._setup_ui()

    def _setup_ui(self):
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True)

        toolbar = ttk.Frame(main_frame)
        toolbar.pack(fill=tk.X)
        ttk.Button(toolbar, text="全选", command=self.select_all, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="全不选", command=self.select_none, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="选在线", command=self.select_online, width=8).pack(side=tk.LEFT, padx=2)
        self.stats_label = ttk.Label(toolbar, text="设备:0 在线:0 选中:0")
        self.stats_label.pack(side=tk.RIGHT, padx=6)

        cols = ("选择", "序号", "IP", "端口", "状态", "最后消息", "device_index")
        self.tree = ttk.Treeview(main_frame, columns=cols, show="headings")
        for c in cols[:-1]:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=120)
            self.tree.column("选择", width=50, anchor="center")
            self.tree.column("序号", width=50, anchor="center")
            self.tree.column("device_index", width=0, stretch=False)
            self.tree.pack(fill=tk.BOTH, expand=True)

    def load_devices(self, devices):
        self.devices = devices
        self.tree.delete(*self.tree.get_children())
        self.checkbox_vars.clear()
        self._item_by_index.clear()
        for d in devices:
            self._insert_device(d)
        self.update_stats()

    def _insert_device(self, d: DeviceInfo):
        values = ("✓" if d.selected else "", str(d.index+1), d.ip, d.port, d.status, d.last_message[:60], d.index)
        iid = self.tree.insert("", tk.END, values=values)
        self._item_by_index[d.index] = iid

    def update_device_status(self, device_index, status, online=None, message=""):
        if device_index < len(self.devices):
            d = self.devices[device_index]
            d.status = status
            if online is not None:
                d.online = online
            if message:
                d.last_message = message
            iid = self._item_by_index.get(device_index)
            if iid:
                vals = list(self.tree.item(iid, 'values'))
                vals[4] = status
                vals[5] = message[:60]
                self.tree.item(iid, values=vals)

    def update_stats(self):
        total = len(self.devices)
        online = sum(1 for d in self.devices if d.online)
        selected = sum(1 for d in self.devices if d.selected)
        self.stats_label.config(text=f"设备:{total} 在线:{online} 选中:{selected}")

    def get_selected_devices(self):
        return [d for d in self.devices if d.selected]

    def select_all(self):
        for d in self.devices:
            d.selected = True
        self.load_devices(self.devices)

    def select_none(self):
        for d in self.devices:
            d.selected = False
        self.load_devices(self.devices)

    def select_online(self):
        for d in self.devices:
            d.selected = bool(d.online)
        self.load_devices(self.devices)


class LogPanel(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X)
        # 移除原有的按钮
        self.text = scrolledtext.ScrolledText(self, height=18)
        self.text.pack(fill=tk.BOTH, expand=True)

    def log(self, msg, level="INFO"):
        from datetime import datetime
        ts = datetime.now().strftime('%H:%M:%S')
        self.text.insert(tk.END, f"[{ts}] [{level}] {msg}\n")
        self.text.see(tk.END)

    def clear(self):
        self.text.delete('1.0', tk.END)

    def save(self):
        fn = filedialog.asksaveasfilename(defaultextension='.log')
        if not fn:
            return
        with open(fn, 'w', encoding='utf-8') as f:
            f.write(self.text.get('1.0', tk.END))

    def open_log_directory(self):
        """打开日志目录"""
        if not self.log_manager.open_log_directory():
            self.log_message("打开日志目录失败，目录可能不存在", "ERROR")

    def _save_log(self):
        """保存日志按钮的回调函数"""
        self.save()

    def _clear_log(self):
        """清空日志按钮的回调函数"""
        self.clear()


class ConfigTab(ttk.Frame):
    def __init__(self, parent, config, save_callback=None):
        super().__init__(parent)
        self.config = config
        self.save_callback = save_callback
        self._setup_ui()
        self.load_config_to_ui()

    def _setup_ui(self):
        # 创建一个容器框架用于放置所有控件
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # CGI命令文本框
        self.cmds_text = scrolledtext.ScrolledText(main_frame, height=10)
        self.cmds_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # 配置参数框架
        params_frame = ttk.LabelFrame(main_frame, text="配置参数", padding=10)
        params_frame.pack(fill=tk.X, pady=(0, 10))

        # 第一行：HTTP超时和配置并发数
        row1 = ttk.Frame(params_frame)
        row1.pack(fill=tk.X, pady=2)
        
        ttk.Label(row1, text="HTTP超时(ms):", width=15, anchor=tk.W).pack(side=tk.LEFT)
        self.timeout_var = tk.StringVar(value=str(self.config.get('timeout', 1000)))
        ttk.Entry(row1, textvariable=self.timeout_var, width=10).pack(side=tk.LEFT, padx=(0, 20))
        
        ttk.Label(row1, text="配置并发数:", width=12, anchor=tk.W).pack(side=tk.LEFT)
        self.concurrent_var = tk.StringVar(value=str(self.config.get('config_concurrent', 50)))
        ttk.Entry(row1, textvariable=self.concurrent_var, width=10).pack(side=tk.LEFT)

        # 第二行：Ping超时和Ping并发数
        row2 = ttk.Frame(params_frame)
        row2.pack(fill=tk.X, pady=2)
        
        ttk.Label(row2, text="Ping超时(ms):", width=15, anchor=tk.W).pack(side=tk.LEFT)
        self.ping_timeout_var = tk.StringVar(value=str(self.config.get('ping_timeout', 200)))
        ttk.Entry(row2, textvariable=self.ping_timeout_var, width=10).pack(side=tk.LEFT, padx=(0, 20))
        
        ttk.Label(row2, text="Ping并发数:", width=12, anchor=tk.W).pack(side=tk.LEFT)
        self.ping_concurrent_var = tk.StringVar(value=str(self.config.get('ping_concurrent', 150)))
        ttk.Entry(row2, textvariable=self.ping_concurrent_var, width=10).pack(side=tk.LEFT)

        # 第三行：认证方式和执行策略
        row3 = ttk.Frame(params_frame)
        row3.pack(fill=tk.X, pady=2)
        
        ttk.Label(row3, text="认证方式:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        self.auth_method_var = tk.StringVar(value=self.config.get('auth_method', 'digest'))
        auth_method_combo = ttk.Combobox(row3, textvariable=self.auth_method_var, 
                                        values=['digest', 'basic'], width=10, state='readonly')
        auth_method_combo.pack(side=tk.LEFT, padx=(0, 20))
        
        ttk.Label(row3, text="执行策略:", width=12, anchor=tk.W).pack(side=tk.LEFT)
        self.exec_strategy_var = tk.StringVar(value=self.config.get('exec_strategy', 'device_first'))
        exec_strategy_combo = ttk.Combobox(row3, textvariable=self.exec_strategy_var,
                                          values=['device_first', 'command_first'], width=15, state='readonly')
        exec_strategy_combo.pack(side=tk.LEFT)

        # 第四行：复选框选项
        row4 = ttk.Frame(params_frame)
        row4.pack(fill=tk.X, pady=2)
        
        self.enable_precheck_var = tk.BooleanVar(value=self.config.get('enable_precheck', True))
        ttk.Checkbutton(row4, text="启用预检查", variable=self.enable_precheck_var).pack(side=tk.LEFT, padx=(0, 15))
        
        self.auto_skip_offline_var = tk.BooleanVar(value=self.config.get('auto_skip_offline', True))
        ttk.Checkbutton(row4, text="自动跳过离线设备", variable=self.auto_skip_offline_var).pack(side=tk.LEFT, padx=(0, 15))
        
        self.verify_ssl_var = tk.BooleanVar(value=self.config.get('verify_ssl', False))
        ttk.Checkbutton(row4, text="验证SSL证书", variable=self.verify_ssl_var).pack(side=tk.LEFT)

    def load_config_to_ui(self):
        # 加载CGI命令
        cmds = self.config.get('cgi_commands', [])
        self.cmds_text.delete('1.0', tk.END)
        self.cmds_text.insert('1.0', '\n'.join(cmds))
        
        # 加载其他配置项
        self.timeout_var.set(str(self.config.get('timeout', 1000)))
        self.concurrent_var.set(str(self.config.get('config_concurrent', 50)))
        self.ping_timeout_var.set(str(self.config.get('ping_timeout', 200)))
        self.ping_concurrent_var.set(str(self.config.get('ping_concurrent', 150)))
        self.auth_method_var.set(self.config.get('auth_method', 'digest'))
        self.exec_strategy_var.set(self.config.get('exec_strategy', 'device_first'))
        self.enable_precheck_var.set(self.config.get('enable_precheck', True))
        self.auto_skip_offline_var.set(self.config.get('auto_skip_offline', True))
        self.verify_ssl_var.set(self.config.get('verify_ssl', False))

    def save_ui_to_config(self):
        # 保存CGI命令
        text = self.cmds_text.get('1.0', tk.END).strip()
        self.config['cgi_commands'] = [l.strip() for l in text.splitlines() if l.strip()]
        
        # 保存其他配置项
        try:
            self.config['timeout'] = int(self.timeout_var.get())
        except Exception:
            pass
        try:
            self.config['config_concurrent'] = int(self.concurrent_var.get())
        except Exception:
            pass
        try:
            self.config['ping_timeout'] = int(self.ping_timeout_var.get())
        except Exception:
            pass
        try:
            self.config['ping_concurrent'] = int(self.ping_concurrent_var.get())
        except Exception:
            pass
            
        self.config['auth_method'] = self.auth_method_var.get()
        self.config['exec_strategy'] = self.exec_strategy_var.get()
        self.config['enable_precheck'] = self.enable_precheck_var.get()
        self.config['auto_skip_offline'] = self.auto_skip_offline_var.get()
        self.config['verify_ssl'] = self.verify_ssl_var.get()
        
        if self.save_callback:
            self.save_callback(self.config)


class AggregateReportTab(ttk.Frame):
    """聚合报表展示 Tab"""
    def __init__(self, parent):
        super().__init__(parent)
        self.report = None
        self._setup_ui()

    def _setup_ui(self):
        self.text = scrolledtext.ScrolledText(self, height=22, font=('Consolas', 9))
        self.text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.text.insert(tk.END, "聚合报表将在配置执行完成后自动生成。\n")

    def show_report(self, report: AggregateReport):
        """显示聚合报表内容"""
        self.report = report
        self.text.delete('1.0', tk.END)
        text = AggregateResultCollector.to_summary_text(report)
        self.text.insert(tk.END, text)

    def clear_report(self):
        """清空报表"""
        self.report = None
        self.text.delete('1.0', tk.END)
        self.text.insert(tk.END, "聚合报表将在配置执行完成后自动生成。\n")


class DahuaConfigApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('DaHua CGI 批量配置 - V9.6-alpha')
        self.geometry('1100x700')

        self.config_data = ConfigManager.load_config()
        self.log_manager = LogManager()
        self.device_loader = DeviceLoader(self.log_manager)
        self.detector = DeviceDetector(self.config_data, self.log_manager, log_callback=self.log_message)

        self.executor = None
        self.executor_thread = None
        self._start_time = None

        self._build_ui()

    def _build_ui(self):
        # 创建顶部按钮框架并将其放在最上方
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, side=tk.TOP)
        
        # 左侧按钮
        ttk.Button(btn_frame, text='加载 Excel', command=self.load_excel).pack(side=tk.LEFT, padx=4, pady=6)
        ttk.Button(btn_frame, text='下载模板', command=self.download_template).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text='Ping 检测', command=self.start_detection).pack(side=tk.LEFT, padx=4)
        self.start_btn = ttk.Button(btn_frame, text='开始配置', command=self.start_configuration)
        self.start_btn.pack(side=tk.LEFT, padx=4)
        self.stop_btn = ttk.Button(btn_frame, text='停止', command=self.stop_configuration, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=4)

        # 新增的日志按钮（使用lambda避免直接引用未创建的对象）
        self.save_log_btn = ttk.Button(btn_frame, text='保存日志', command=lambda: self._save_log())
        self.clear_log_btn = ttk.Button(btn_frame, text='清空显示', command=lambda: self._clear_log())
        
        # 右侧按钮（所有按钮都始终显示）
        self.save_config_btn = ttk.Button(btn_frame, text='保存配置', command=lambda: self.config_tab.save_ui_to_config())
        self.reload_config_btn = ttk.Button(btn_frame, text='重载配置', command=self.reload_config)
        self.reset_config_btn = ttk.Button(btn_frame, text='默认配置', command=self.reset_to_default)
        self.view_failures_btn = ttk.Button(btn_frame, text='查看失败', command=self.view_failure_logs)
        self.open_logs_btn = ttk.Button(btn_frame, text='日志目录', command=self.open_log_directory)
        self.export_report_btn = ttk.Button(btn_frame, text='导出报表', command=self.export_report)

        
        # 按固定顺序排列所有按钮（将新的日志按钮放在保存配置按钮前面）
        self.export_report_btn.pack(side=tk.RIGHT, padx=4)
        self.open_logs_btn.pack(side=tk.RIGHT, padx=4)
        self.view_failures_btn.pack(side=tk.RIGHT, padx=4)
        self.reset_config_btn.pack(side=tk.RIGHT, padx=4)
        self.reload_config_btn.pack(side=tk.RIGHT, padx=4)
        self.save_config_btn.pack(side=tk.RIGHT, padx=4)
        self.clear_log_btn.pack(side=tk.RIGHT, padx=4)
        self.save_log_btn.pack(side=tk.RIGHT, padx=4)

        # 主界面PanedWindow
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
        left = ttk.Frame(paned, width=420)
        right = ttk.Frame(paned)
        paned.add(left, weight=1)
        paned.add(right, weight=3)
        
        # 设备表
        self.device_table = DeviceTableFrame(left, log_callback=self.log_message)
        self.device_table.pack(fill=tk.BOTH, expand=True)
        
        # 右侧 notebook
        self.nb = ttk.Notebook(right)
        self.nb.pack(fill=tk.BOTH, expand=True)
        self.config_tab = ConfigTab(self.nb, self.config_data, save_callback=self.save_config)
        self.log_panel = LogPanel(self.nb)
        self.query_tab = QueryTab(self.nb, self)
        self.report_tab = AggregateReportTab(self.nb)
        self.nb.add(self.log_panel, text='运行日志')
        self.nb.add(self.config_tab, text='配置CGI')
        self.nb.add(self.query_tab, text='CGI查询')
        self.nb.add(self.report_tab, text='聚合报表')

        
        # 创建底部进度条框架
        progress_frame = ttk.Frame(self)
        progress_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=2)
        
        # 添加进度条
        self.progress_bar = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, length=200, mode='determinate')
        self.progress_bar.pack(fill=tk.X, expand=True, side=tk.TOP)
        
        # 进度文本标签（居中显示在进度条上，背景透明）
        self.progress_text_var = tk.StringVar(value='0%')
        # 使用tk.Label而不是ttk.Label来更好地控制背景色
        self.progress_text_label = tk.Label(
            progress_frame, 
            textvariable=self.progress_text_var,
            bg=self.cget('bg'),  # 设置背景色为窗口背景色（透明效果）
            fg='black',  # 文字颜色为黑色
            font=('Arial', 9)  # 设置字体
        )
        self.progress_text_label.place(relx=0.5, rely=0.5, anchor='center')
            
        # 底部操作条
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X)
        
    def _save_log(self):
        """保存日志按钮的回调函数"""
        if hasattr(self, 'log_panel') and self.log_panel:
            self.log_panel.save()

    def _clear_log(self):
        """清空日志按钮的回调函数"""
        if hasattr(self, 'log_panel') and self.log_panel:
            self.log_panel.clear()
        
    def log_message(self, message, level='INFO'):
        try:
            self.log_panel.log(message, level)
            self.log_manager.log_detailed(message, level)
        except Exception:
            pass

    def save_config(self, config_dict):
        ok = ConfigManager.save_config(config_dict)
        if ok:
            self.log_message('配置已保存', 'SUCCESS')
        else:
            self.log_message('保存配置失败', 'ERROR')

    def load_excel(self):
        fn = filedialog.askopenfilename(title='选择设备Excel', filetypes=[('Excel文件', '*.xlsx;*.xls'), ('所有文件', '*.*')])
        if not fn:
            return

        def _load():
            try:
                devices, count = self.device_loader.load_from_excel(fn)
                # devices indices are normalized by loader
                self.device_table.load_devices(devices)
                self.log_message(f'已加载 {count} 台设备', 'SUCCESS')
            except ValueError as e:
                error_msg = str(e)
                self.log_message(f'加载 Excel 失败: {error_msg}', 'ERROR')
                # 严格校验失败时弹窗提示
                self.after(0, lambda: messagebox.showerror('模板错误',
                    f'{error_msg}\n\n请点击「下载模板」按钮获取标准模板'))
            except Exception as e:
                self.log_message(f'加载 Excel 失败: {e}', 'ERROR')

        threading.Thread(target=_load, daemon=True).start()

    def download_template(self):
        """下载Excel导入模板"""
        template_path = os.path.join(os.path.dirname(__file__), 'templates', 'device_import_template.xlsx')
        if not os.path.exists(template_path):
            messagebox.showerror('错误', '模板文件不存在')
            return
        
        fn = filedialog.asksaveasfilename(
            title='保存模板',
            defaultextension='.xlsx',
            initialfile='device_import_template.xlsx',
            filetypes=[('Excel 文件', '*.xlsx')]
        )
        if not fn:
            return
        
        try:
            import shutil
            shutil.copy2(template_path, fn)
            self.log_message(f'模板已保存到: {fn}', 'SUCCESS')
        except Exception as e:
            self.log_message(f'保存模板失败: {e}', 'ERROR')

    def start_detection(self):
        devices = self.device_table.devices
        if not devices:
            messagebox.showwarning('提示', '请先加载设备列表')
            return
    
        def progress_cb(tag, progress, stats):
            # stats.devices_updated 是在 device_manager 中构造的
            for up in stats.get('devices_updated', []):
                idx = up.get('index')
                self.device_table.update_device_status(idx, up.get('status', ''), online=up.get('online', False), message=up.get('message', ''))
            self.device_table.update_stats()
            
            # 更新进度条和文本（简化文本格式）
            self.progress_bar['value'] = progress
            self.progress_text_var.set(f"{progress:.1f}%")
    
        def _detect():
            try:
                self.log_message('开始 Ping 检测', 'INFO')
                online, offline = self.detector.detect_devices(devices, progress_callback=progress_cb, stop_callback=lambda: False)
                self.log_message(f'检测完成: 在线 {online} 台, 离线 {offline} 台', 'SUCCESS')
                # 检测完成后设置进度为100%
                self.progress_bar['value'] = 100
                self.progress_text_var.set("100%")
            except Exception as e:
                self.log_message(f'检测异常: {e}', 'ERROR')
                # 出错时重置进度
                self.progress_bar['value'] = 0
                self.progress_text_var.set("0%")
    
        threading.Thread(target=_detect, daemon=True).start()

    def start_configuration(self):
        devices = self.device_table.get_selected_devices()
        if not devices:
            messagebox.showwarning('提示', '请先选择要配置的设备')
            return
    
        # 确保 UI 上的配置被保存到 config
        self.config_tab.save_ui_to_config()
    
        # 设置按钮状态：禁用开始按钮，启用停止按钮
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        
        # 创建执行器（启用异步路径）
        self.executor = ConfigExecutor(self.config_data, self.log_manager, log_callback=self.log_message, use_async=True)
    
        def progress_cb(tag, progress, stats):
            # 在主线程更新UI
            def _ui_update():
                for up in stats.get('devices_updated', []):
                    idx = up.get('index')
                    self.device_table.update_device_status(idx, up.get('status', ''), online=up.get('online', False), message=up.get('message', ''))
                # 更新进度条和文本（简化文本格式）
                self.progress_bar['value'] = progress
                self.progress_text_var.set(f"{progress:.1f}%")
                self.log_message(f"进度: {progress:.1f}% ({stats.get('completed')}/{stats.get('total')})", 'DEBUG')
                self.device_table.update_stats()
    
            try:
                self.after(0, _ui_update)
            except Exception:
                _ui_update()
    
        from datetime import datetime
        self._start_time = datetime.now()
    
        def _run():
            try:
                self.log_message('开始批量配置', 'INFO')
                res = self.executor.execute_batch(devices, mode=self.config_data.get('default_mode','standard'), exec_strategy=self.config_data.get('exec_strategy','device_first'), progress_callback=progress_cb, stop_callback=self.executor._is_stopped)
                self.log_message(f'配置完成，结果设备数: {len(res)}', 'SUCCESS')
                
                # 生成聚合报表
                try:
                    report = AggregateResultCollector.collect(res, devices, self._start_time)
                    def _show_report():
                        try:
                            self.report_tab.show_report(report)
                            self.log_message(f'聚合报表已生成: 成功率 {report.success_rate:.1f}%', 'SUCCESS')
                        except Exception:
                            pass
                    try:
                        self.after(0, _show_report)
                    except Exception:
                        _show_report()
                except Exception as e:
                    self.log_message(f'生成聚合报表失败: {e}', 'ERROR')
            except Exception as e:
                self.log_message(f'配置异常: {e}', 'ERROR')
            finally:
                # 任务完成后在主线程恢复按钮状态并显示100%
                def _finish_ui():
                    try:
                        self.start_btn.config(state=tk.NORMAL)
                        self.stop_btn.config(state=tk.DISABLED)
                        self.progress_bar['value'] = 100
                        self.progress_text_var.set('100%')
                    except Exception:
                        pass
                try:
                    self.after(0, _finish_ui)
                except Exception:
                    _finish_ui()
    
        self.executor_thread = threading.Thread(target=_run, daemon=True)
        self.executor_thread.start()

    def stop_configuration(self):
        try:
            if self.executor:
                self.executor.stop()
                # 立即刷新UI以反映停止状态
                try:
                    # 更新所有设备在UI上的显示
                    for d in (self.device_table.devices or []):
                        self.device_table.update_device_status(d.index, d.status, online=d.online, message=d.last_message)
                    self.device_table.update_stats()
                    self.update_idletasks()
                except Exception:
                    pass
                # 更新按钮状态
                try:
                    self.start_btn.config(state=tk.NORMAL)
                    self.stop_btn.config(state=tk.DISABLED)
                    # 停止时重置进度
                    self.progress_bar['value'] = 0
                    self.progress_text_var.set('0%')
                except Exception:
                    pass
                self.log_message('已请求停止', 'WARNING')
        except Exception as e:
            self.log_message(f'停止请求失败: {e}', 'ERROR')
            
    def export_devices(self):
        """导出设备列表到Excel文件"""
        if not self.device_table.devices:
            messagebox.showwarning('提示', '没有设备可以导出')
            return
            
        filename = filedialog.asksaveasfilename(
            title='导出设备列表',
            defaultextension='.xlsx',
            filetypes=[('Excel文件', '*.xlsx'), ('CSV文件', '*.csv')]
        )
        
        if not filename:
            return
            
        try:
            # 导出逻辑将在后续实现
            self.log_message(f'设备列表已导出到: {filename}', 'SUCCESS')
        except Exception as e:
            self.log_message(f'导出设备列表失败: {e}', 'ERROR')
            
    def import_devices(self):
        """从Excel文件导入设备列表"""
        filename = filedialog.askopenfilename(
            title='导入设备列表',
            filetypes=[('Excel文件', '*.xlsx;*.xls'), ('CSV文件', '*.csv'), ('所有文件', '*.*')]
        )
        
        if not filename:
            return
            
        try:
            # 导入逻辑将在后续实现
            self.log_message(f'设备列表已从 {filename} 导入', 'SUCCESS')
        except Exception as e:
            self.log_message(f'导入设备列表失败: {e}', 'ERROR')
    
    def on_tab_changed(self, event=None):
        """处理标签页切换事件"""
        selected_tab = self.nb.select()
        tab_text = self.nb.tab(selected_tab, "text")
        
        # 根据当前标签页显示相应的按钮，但保持按钮位置固定
        if tab_text == "配置":
            # 在配置页隐藏日志相关的按钮，显示配置相关的按钮
            self.reload_config_btn.pack_forget()
            self.reset_config_btn.pack_forget()
            self.view_failures_btn.pack_forget()
            self.open_logs_btn.pack_forget()
            # 隐藏新增的日志按钮
            self.save_log_btn.pack_forget()
            self.clear_log_btn.pack_forget()
            
            # 重新按固定顺序排列按钮
            self.save_config_btn.pack(side=tk.RIGHT, padx=4)
        elif tab_text == "日志":
            # 在日志页显示所有按钮
            # 重新按固定顺序排列按钮，保持位置一致
            self.save_config_btn.pack(side=tk.RIGHT, padx=4)
            self.open_logs_btn.pack(side=tk.RIGHT, padx=4)
            self.view_failures_btn.pack(side=tk.RIGHT, padx=4)
            self.reset_config_btn.pack(side=tk.RIGHT, padx=4)
            self.reload_config_btn.pack(side=tk.RIGHT, padx=4)
            # 显示新增的日志按钮
            self.clear_log_btn.pack(side=tk.RIGHT, padx=4)
            self.save_log_btn.pack(side=tk.RIGHT, padx=4)

    def reload_config(self):
        """重新加载配置文件"""
        try:
            self.config_data = ConfigManager.load_config()
            self.config_tab.config = self.config_data
            self.config_tab.load_config_to_ui()
            self.log_message("配置已重新加载", "SUCCESS")
        except Exception as e:
            self.log_message(f"重新加载配置失败: {e}", "ERROR")

    def reset_to_default(self):
        """恢复默认配置"""
        # 弹出确认对话框
        result = messagebox.askyesno("确认", "确定要恢复默认配置吗？这将丢失当前的所有配置。")
        if result:
            try:
                # 加载默认配置
                self.config_data = ConfigManager.get_default_config()
                self.config_tab.config = self.config_data
                self.config_tab.load_config_to_ui()
                self.log_message("已恢复默认配置", "SUCCESS")
            except Exception as e:
                self.log_message(f"恢复默认配置失败: {e}", "ERROR")
    def view_failure_logs(self):
        """查看失败日志"""
        if not self.log_manager.open_failure_logs():
            self.log_message("打开失败日志失败，文件可能不存在", "ERROR")

    def open_log_directory(self):
        """打开日志目录"""
        if not self.log_manager.open_log_directory():
            self.log_message("打开日志目录失败，目录可能不存在", "ERROR")

    def export_report(self):
        """导出聚合报表"""
        if not self.report_tab.report:
            messagebox.showwarning('提示', '没有报表可导出，请先执行配置')
            return

        filename = filedialog.asksaveasfilename(
            title='导出聚合报表',
            defaultextension='.csv',
            filetypes=[('CSV文件', '*.csv'), ('Excel文件', '*.xlsx'), ('文本文件', '*.txt')]
        )

        if not filename:
            return

        try:
            report = self.report_tab.report
            ext = os.path.splitext(filename)[1].lower()

            if ext == '.csv':
                import csv
                with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    writer.writerow(['聚合报表导出'])
                    writer.writerow(['总览'])
                    overview = AggregateResultCollector.to_dict(report)['总览']
                    for k, v in overview.items():
                        writer.writerow([k, v])
                    writer.writerow([])
                    writer.writerow(['设备维度'])
                    writer.writerow(['IP', '端口', '状态', '总命令', '成功', '失败', '耗时(秒)', '最后消息'])
                    for d in report.per_device:
                        writer.writerow([d.ip, d.port, d.status, d.total_commands, d.success, d.failed, round(d.duration, 2), d.last_message])
                    writer.writerow([])
                    writer.writerow(['命令维度'])
                    writer.writerow(['命令', '总尝试', '成功', '失败', '平均耗时(秒)', '失败率(%)'])
                    for cmd_name, cs in report.per_command.items():
                        writer.writerow([cmd_name, cs.total_attempts, cs.success, cs.failed, round(cs.avg_duration, 2), round(cs.failure_rate, 2)])
            elif ext == '.xlsx':
                try:
                    import openpyxl
                except ImportError:
                    openpyxl = None
                if openpyxl:
                    wb = openpyxl.Workbook()
                    ws = wb.active
                    ws.title = '聚合报表'
                    ws.append(['聚合报表导出'])
                    ws.append(['总览'])
                    overview = AggregateResultCollector.to_dict(report)['总览']
                    for k, v in overview.items():
                        ws.append([k, v])
                    ws.append([])
                    ws.append(['设备维度'])
                    ws.append(['IP', '端口', '状态', '总命令', '成功', '失败', '耗时(秒)', '最后消息'])
                    for d in report.per_device:
                        ws.append([d.ip, d.port, d.status, d.total_commands, d.success, d.failed, round(d.duration, 2), d.last_message])
                    ws.append([])
                    ws.append(['命令维度'])
                    ws.append(['命令', '总尝试', '成功', '失败', '平均耗时(秒)', '失败率(%)'])
                    for cmd_name, cs in report.per_command.items():
                        ws.append([cmd_name, cs.total_attempts, cs.success, cs.failed, round(cs.avg_duration, 2), round(cs.failure_rate, 2)])
                    wb.save(filename)
                else:
                    # fallback to text file
                    filename = os.path.splitext(filename)[0] + '.txt'
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(AggregateResultCollector.to_summary_text(report))
            else:
                # txt
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(AggregateResultCollector.to_summary_text(report))

            self.log_message(f'报表已导出到: {filename}', 'SUCCESS')
        except Exception as e:
            self.log_message(f'导出报表失败: {e}', 'ERROR')


class QueryTab(ttk.Frame):
    """CGI查询 Tab — 批量查询设备CGI命令并导出结果"""
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.query_executor = None
        self.query_results_df = None
        self._setup_ui()

    def _setup_ui(self):
        # 命令输入区
        cmd_frame = ttk.LabelFrame(self, text='CGI查询命令（每行一个）')
        cmd_frame.pack(fill=tk.BOTH, expand=False, padx=5, pady=5)

        self.cmd_text = scrolledtext.ScrolledText(cmd_frame, height=8, font=('Consolas', 9))
        self.cmd_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.cmd_text.insert(tk.END, '# 纯命令名模式（自动拼接标准CGI URL）\n')
        self.cmd_text.insert(tk.END, 'Alarm\n')
        self.cmd_text.insert(tk.END, 'VideoInMode\n')
        self.cmd_text.insert(tk.END, 'VideoInChannel\n')
        self.cmd_text.insert(tk.END, '# 自定义URL模式（支持{{IP}}变量替换）\n')
        self.cmd_text.insert(tk.END, 'http://{{IP}}:{{port}}/cgi-bin/configManager.cgi?action=getConfig&name=RecordMode\n')

        # 按钮区
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        self.query_btn = ttk.Button(btn_frame, text='开始查询', command=self.start_query)
        self.query_btn.pack(side=tk.LEFT, padx=4)

        self.export_btn = ttk.Button(btn_frame, text='导出结果', command=self.export_results, state=tk.DISABLED)
        self.export_btn.pack(side=tk.LEFT, padx=4)

        # 进度条
        self.query_progress = ttk.Progressbar(btn_frame, orient=tk.HORIZONTAL, length=300, mode='determinate')
        self.query_progress.pack(side=tk.LEFT, padx=20, fill=tk.X, expand=True)

        self.progress_label = ttk.Label(btn_frame, text='0%')
        self.progress_label.pack(side=tk.LEFT, padx=4)

        # 结果表格
        result_frame = ttk.LabelFrame(self, text='查询结果')
        result_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 创建容器Frame支持横向滚动
        table_container = ttk.Frame(result_frame)
        table_container.pack(fill=tk.BOTH, expand=True)

        # Treeview + 横向滚动（使用pack布局避免测试mock的grid兼容问题）
        self.result_tree = ttk.Treeview(table_container, show='headings', height=15)
        vsb = ttk.Scrollbar(table_container, orient=tk.VERTICAL, command=self.result_tree.yview)
        hsb = ttk.Scrollbar(table_container, orient=tk.HORIZONTAL, command=self.result_tree.xview)
        try:
            self.result_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        except Exception:
            pass
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.result_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.result_tree.insert('', tk.END, values=('查询结果将在此显示',))

    def get_devices(self):
        """获取当前设备列表"""
        return self.app.device_table.devices if self.app and hasattr(self.app, 'device_table') else []

    def start_query(self):
        """开始CGI查询"""
        devices = self.get_devices()
        if not devices:
            messagebox.showwarning('提示', '请先加载设备列表')
            return

        # 读取命令
        raw_text = self.cmd_text.get('1.0', tk.END).strip()
        commands = []
        for line in raw_text.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                commands.append(line)

        if not commands:
            messagebox.showwarning('提示', '请输入CGI查询命令')
            return

        self.query_btn.config(state=tk.DISABLED)
        self.export_btn.config(state=tk.DISABLED)
        self.query_progress['value'] = 0
        self.progress_label.config(text='0%')

        def progress_cb(progress):
            self.after(0, lambda: self._update_progress(progress))

        def _run():
            try:
                self.query_executor = CgiQueryExecutor(
                    self.app.config_data,
                    self.app.log_manager,
                    log_callback=self.app.log_message
                )
                df = self.query_executor.execute_query(
                    devices, commands,
                    progress_callback=progress_cb,
                )
                self.query_results_df = df
                self.after(0, self._show_results)
            except Exception as e:
                self.after(0, lambda: self.app.log_message(f'查询失败: {e}', 'ERROR'))
                self.after(0, lambda: self.query_btn.config(state=tk.NORMAL))

        threading.Thread(target=_run, daemon=True).start()

    def _update_progress(self, progress):
        self.query_progress['value'] = progress
        self.progress_label.config(text=f'{progress:.1f}%')

    def _show_results(self):
        """在主线程更新结果表格"""
        df = self.query_results_df
        if df is None or df.empty:
            self.app.log_message('查询结果为空', 'WARNING')
            self.query_btn.config(state=tk.NORMAL)
            return

        # 清空旧数据
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)

        # 设置列
        columns = list(df.columns)
        self.result_tree['columns'] = columns
        for col in columns:
            self.result_tree.heading(col, text=col)
            self.result_tree.column(col, width=120, minwidth=80)
            if col in ('Ping状态', '账号验证'):
                self.result_tree.column(col, width=100)

        # 插入数据
        for _, row in df.iterrows():
            values = [str(row[col]) if pd.notna(row[col]) else '' for col in columns]
            self.result_tree.insert('', tk.END, values=values)

        self.query_progress['value'] = 100
        self.progress_label.config(text='100%')
        self.query_btn.config(state=tk.NORMAL)
        self.export_btn.config(state=tk.NORMAL)
        self.app.log_message(f'查询完成: {len(df)} 台设备', 'SUCCESS')

    def export_results(self):
        """导出查询结果为Excel"""
        if self.query_results_df is None or self.query_results_df.empty:
            messagebox.showwarning('提示', '没有查询结果可导出')
            return

        default_name = f'CGI查询结果_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        fn = filedialog.asksaveasfilename(
            title='导出查询结果',
            defaultextension='.xlsx',
            initialfile=default_name,
            filetypes=[('Excel 文件', '*.xlsx'), ('CSV 文件', '*.csv')]
        )
        if not fn:
            return

        try:
            if self.query_executor is None:
                self.query_executor = CgiQueryExecutor(
                    self.app.config_data,
                    self.app.log_manager,
                    log_callback=self.app.log_message
                )
            saved = self.query_executor.export_to_excel(self.query_results_df, fn)
            self.app.log_message(f'结果已导出到: {saved}', 'SUCCESS')
        except Exception as e:
            self.app.log_message(f'导出失败: {e}', 'ERROR')


if __name__ == '__main__':
    app = DahuaConfigApp()
    app.mainloop()