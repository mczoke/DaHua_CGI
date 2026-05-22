# 占位文件：此模块在 V9.5 中临时承载从 V9.4.1 复制的 DahuaConfigApp 定义
# 我会把原始的 DahuaConfigApp（来自 V9.4.1/main.py）复制到此处，
# 然后分阶段把 ConfigExecutor 替换为异步实现。

from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading

# 为了保持文件较短，这里从 V9.4.1 中按需复制了核心类的骨架：
class DahuaConfigApp:
    def __init__(self, root):
        self.root = root
        self.root.title("大华摄像机批量配置工具 v9.5 (占位)")
        self.root.geometry("1360x850")
        self.init_app()
        self.setup_ui()
        self.log_message("应用程序启动完成", "SUCCESS")

    def init_app(self):
        from utils.config_manager import ConfigManager
        from utils.log_manager import LogManager
        self.config = ConfigManager.load_config()
        self.log_manager = LogManager()
        self.devices = []
        self.is_loading = False
        self.is_detecting = False
        self.is_configuring = False
        self.stop_detection_flag = False
        self.stop_configuration_flag = False
        self._pending_device_updates = {}
        self._pending_update_scheduled = False


# 从 V9.4.1 复制过来的 UI 组件：DeviceTableFrame 和 LogPanel（已适配）
class DeviceTableFrame(ttk.Frame):
    """设备表格框架（简化复制自 v9.4.x）"""
    def __init__(self, parent, log_callback=None):
        super().__init__(parent)
        self.devices = []
        self.checkbox_vars = {}
        self._item_by_index = {}
        self.log_callback = log_callback
        self._setup_ui()

    def _setup_ui(self):
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # 原有工具栏
        toolbar = ttk.Frame(main_frame)
        toolbar.pack(fill=tk.X, pady=(0,5))

        ttk.Button(toolbar, text="全选", command=self.select_all, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="全不选", command=self.select_none, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="选在线", command=self.select_online, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="刷新", command=self.refresh, width=8).pack(side=tk.RIGHT, padx=2)

        self.stats_label = ttk.Label(toolbar, text="设备: 0 | 在线: 0 | 离线: 0 | 选中: 0")
        self.stats_label.pack(side=tk.RIGHT, padx=10)
        
        # 新增按钮工具栏
        button_toolbar = ttk.Frame(main_frame)
        button_toolbar.pack(fill=tk.X, pady=(0,5))
        
        ttk.Button(button_toolbar, text="导出选中", width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_toolbar, text="删除选中", width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_toolbar, text="批量修改", width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_toolbar, text="设备详情", width=10).pack(side=tk.LEFT, padx=2)

        tree_container = ttk.Frame(main_frame)
        tree_container.pack(fill=tk.BOTH, expand=True)

        columns = ("选择", "序号", "IP地址", "端口", "状态", "最后消息", "device_index")
        self.tree = ttk.Treeview(tree_container, columns=columns, show="headings", height=20)
        self.tree.column("device_index", width=0, stretch=False)
        self.tree.heading("device_index", text="")

        col_configs = {
            "选择": {"width": 40, "anchor": "center"},
            "序号": {"width": 40, "anchor": "center"},
            "IP地址": {"width": 100, "anchor": "center"},
            "端口": {"width": 60, "anchor": "center"},
            "状态": {"width": 80, "anchor": "center"},
            "最后消息": {"width": 160, "anchor": "w"}
        }

        for col in columns[:-1]:
            self.tree.heading(col, text=col)
            config = col_configs.get(col, {"width":100, "anchor":"center"})
            self.tree.column(col, width=config["width"], anchor=config["anchor"])

        vsb = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)

        self.tree.tag_configure("online", foreground="dark green")
        self.tree.tag_configure("offline", foreground="red")
        self.tree.tag_configure("success", foreground="dark green", font=("",9,"bold"))
        self.tree.tag_configure("failed", foreground="dark red", font=("",9,"bold"))
        self.tree.tag_configure("configuring", foreground="orange", font=("",9,"bold"))

        self.tree.bind("<Button-1>", self.on_tree_click)

    def load_devices(self, devices):
        self.devices = devices
        self.tree.delete(*self.tree.get_children())
        self.checkbox_vars.clear()
        self._item_by_index.clear()
        for device in devices:
            self.add_device_row(device)
        self.update_stats()

    def add_device_row(self, device):
        var = tk.BooleanVar(value=device.selected)
        self.checkbox_vars[device.index] = var
        values = (
            "✓" if device.selected else "",
            str(device.index + 1),
            device.ip,
            device.port,
            device.status,
            device.last_message[:40] if device.last_message else "",
            device.index
        )
        item_id = self.tree.insert("", tk.END, values=values)
        self._item_by_index[device.index] = item_id
        tags = self.get_device_tags(device)
        if tags:
            self.tree.item(item_id, tags=tags)
        self.tree.set(item_id, "device_index", device.index)

    def get_device_tags(self, device):
        tags = []
        if device.status == "在线":
            tags.append("online")
        elif device.status == "离线":
            tags.append("offline")
        elif device.status == "配置中":
            tags.append("configuring")
        elif device.status == "成功":
            tags.append("success")
        elif device.status in ["失败", "检测失败", "执行异常"]:
            tags.append("failed")
        return tags

    def on_tree_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.tree.identify_column(event.x)
            item = self.tree.identify_row(event.y)
            if column == "#1" and item:
                values = self.tree.item(item, "values")
                if values and len(values) >= 7:
                    index = int(values[6])
                    var = self.checkbox_vars.get(index)
                    if var:
                        new_value = not var.get()
                        var.set(new_value)
                        if index < len(self.devices):
                            self.devices[index].selected = new_value
                        new_values = list(values)
                        new_values[0] = "✓" if new_value else ""
                        self.tree.item(item, values=new_values)
                        self.update_stats()

    def select_all(self):
        for index, var in self.checkbox_vars.items():
            var.set(True)
            if index < len(self.devices):
                self.devices[index].selected = True
        for item in self.tree.get_children():
            self.tree.set(item, "选择", "✓")
        self.update_stats()

    def select_none(self):
        for index, var in self.checkbox_vars.items():
            var.set(False)
            if index < len(self.devices):
                self.devices[index].selected = False
        for item in self.tree.get_children():
            self.tree.set(item, "选择", "")
        self.update_stats()

    def select_online(self):
        for item in self.tree.get_children():
            values = self.tree.item(item, "values")
            if values and len(values) >= 7:
                index = int(values[6])
                if index < len(self.devices):
                    device = self.devices[index]
                    new_value = device.online and device.status == "在线"
                    var = self.checkbox_vars.get(index)
                    if var:
                        var.set(new_value)
                    device.selected = new_value
        for item in self.tree.get_children():
            values = self.tree.item(item, "values")
            if values and len(values) >= 7:
                index = int(values[6])
                if index < len(self.devices):
                    device = self.devices[index]
                    new_values = list(values)
                    new_values[0] = "✓" if device.selected else ""
                    self.tree.item(item, values=new_values)
        self.update_stats()

    def update_device_status(self, device_index, status, online=None, message=""):
        if device_index < len(self.devices):
            device = self.devices[device_index]
            device.status = status
            if online is not None:
                device.online = online
            if message:
                device.last_message = message
            item_id = self._item_by_index.get(device_index)
            if item_id:
                try:
                    self.tree.set(item_id, "状态", status)
                    self.tree.set(item_id, "最后消息", message[:40] if message else "")
                    tags = self.get_device_tags(device)
                    self.tree.item(item_id, tags=tags)
                except Exception:
                    for item in self.tree.get_children():
                        idx = self.tree.set(item, "device_index")
                        if idx is not None and int(idx) == device_index:
                            self.tree.set(item, "状态", status)
                            self.tree.set(item, "最后消息", message[:40] if message else "")
                            tags = self.get_device_tags(device)
                            self.tree.item(item, tags=tags)
                            break

    def refresh(self):
        for item in self.tree.get_children():
            values = self.tree.item(item, "values")
            if values and len(values) >= 7:
                index = int(values[6])
                if index < len(self.devices):
                    device = self.devices[index]
                    new_values = list(values)
                    new_values[0] = "✓" if device.selected else ""
                    new_values[4] = device.status
                    new_values[5] = device.last_message[:40] if device.last_message else ""
                    self.tree.item(item, values=new_values)
                    tags = self.get_device_tags(device)
                    self.tree.item(item, tags=tags)
        self.update_stats()

    def update_stats(self):
        total = len(self.devices)
        online = sum(1 for d in self.devices if d.online)
        offline = sum(1 for d in self.devices if d.status == "离线")
        selected = sum(1 for d in self.devices if d.selected)
        self.stats_label.config(text=f"设备: {total} | 在线: {online} | 离线: {offline} | 选中: {selected}")

    def get_selected_devices(self):
        return [d for d in self.devices if d.selected]


class LogPanel(ttk.Frame):
    """日志面板（简化复制）"""
    def __init__(self, parent):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, pady=(0,5))
        ttk.Label(toolbar, text="运行日志", font=("",10,"bold")).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="清空", command=self.clear, width=8).pack(side=tk.RIGHT, padx=2)
        ttk.Button(toolbar, text="保存", command=self.save, width=8).pack(side=tk.RIGHT, padx=2)

        self.log_text = scrolledtext.ScrolledText(self, wrap=tk.WORD, font=("Consolas",9), height=25)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.tag_config("INFO", foreground="black")
        self.log_text.tag_config("SUCCESS", foreground="dark green")
        self.log_text.tag_config("WARNING", foreground="orange")
        self.log_text.tag_config("ERROR", foreground="red")
        self.log_text.tag_config("DEBUG", foreground="gray")

    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}\n"
        try:
            self.log_text.insert(tk.END, log_entry, level)
            self.log_text.see(tk.END)
        except:
            pass

    def clear(self):
        self.log_text.delete("1.0", tk.END)

    def save(self):
        filename = filedialog.asksaveasfilename(title="保存日志", defaultextension=".log", filetypes=[("日志文件","*.log"),("文本文件","*.txt"),("所有文件","*.*")])
        if filename:
            try:
                content = self.log_text.get("1.0", tk.END)
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.log(f"日志已保存到: {filename}", "SUCCESS")
            except Exception as e:
                self.log(f"保存日志失败: {e}", "ERROR")

    def setup_ui(self):
        # 这里应完整复制 V9.4.1 的 UI 实现；为避免重复输出，此处保留占位。
        frame = ttk.Frame(self.root)
        ttk.Label(frame, text="V9.5 占位 UI").pack(pady=6)

        btn_frame = ttk.Frame(frame)
        self.start_btn = ttk.Button(btn_frame, text="开始配置(测试)", command=self.start_test_config)
        self.start_btn.pack(side='left', padx=4)
        self.stop_btn = ttk.Button(btn_frame, text="停止配置", command=self.stop_test_config)
        self.stop_btn.pack(side='left', padx=4)
        btn_frame.pack(pady=6)

        # 日志区域
        self.log_box = scrolledtext.ScrolledText(frame, height=10)
        self.log_box.pack(fill='both', expand=True, pady=6)

        frame.pack(fill='both', expand=True)

        # executor reference
        self._current_executor = None
        self._worker_thread = None

    def log_message(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        txt = f"[{timestamp}] [{level}] {message}\n"
        try:
            self.log_box.insert('end', txt)
            self.log_box.see('end')
        except Exception:
            print(txt)

    def start_test_config(self):
        """Start a test configuration run using ConfigExecutor in a background thread."""
        if self._worker_thread and self._worker_thread.is_alive():
            self.log_message("已有配置任务在运行", "WARNING")
            return

        from utils.device_manager import ConfigExecutor, DeviceInfo

        # create two dummy devices (localhost; ensure mock server if you want to test)
        devices = [
            DeviceInfo(index=0, ip='127.0.0.1', port='8080', username='admin', password='admin', online=True, status='在线'),
            DeviceInfo(index=1, ip='127.0.0.1', port='8080', username='admin', password='admin', online=True, status='在线')
        ]

        cfg = {'cgi_commands': ['param=1'], 'config_concurrent': 5, 'timeout': 5000, 'auth_method': 'digest', 'verify_ssl': False}

        def _run():
            try:
                log = self.log_manager
                exe = ConfigExecutor(cfg, log, log_callback=lambda m,l: self.log_message(m,l), use_async=True)
                self._current_executor = exe
                self.log_message('ConfigExecutor 已创建，开始执行', 'INFO')
                res = exe.execute_batch(devices, mode='standard', exec_strategy='device_first', progress_callback=lambda t,p,s: self.log_message(f'进度 {p:.1f}%', 'INFO'), stop_callback=lambda: False)
                self.log_message(f'执行完成: {res}', 'SUCCESS')
            except Exception as e:
                self.log_message(f'执行异常: {e}', 'ERROR')
            finally:
                self._current_executor = None

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        self._worker_thread = t

    def stop_test_config(self):
        """Stop currently running executor if any."""
        if self._current_executor:
            try:
                self._current_executor.stop()
                self.log_message('已发送停止信号给 ConfigExecutor', 'WARNING')
            except Exception as e:
                self.log_message(f'停止请求失败: {e}', 'ERROR')
        else:
            self.log_message('当前没有运行中的配置任务', 'INFO')

# 真正的完整 UI 已在 V9.4.1/main.py 中；如果你确认要把整个 UI 复制到 V9.5，我会继续完整写入。