"""Unit tests for full_app.py — 80%+ coverage target.

Strategy: Mock tkinter such that base classes (Frame, Tk, etc.) can be
instantiated without a display, but still store instance attributes normally.
"""
import sys
import os
import json
import tempfile
import builtins
from unittest.mock import MagicMock, patch, PropertyMock, call, DEFAULT
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


# ============================================================================
# Smart tkinter mocks — allow instantiation, return real instances
# ============================================================================

class _Realish:
    """Dummy that stores __dict__ normally, no tk dependency."""
    pass


class _RealishFrame(_Realish):
    def __init__(self, parent=None, **kw):
        self._children = {}
        self.__dict__.update(kw)
        self.pack = MagicMock()
        self.pack_forget = MagicMock()
        self.config = MagicMock()
        self.heading = MagicMock()
        self.column = MagicMock()
        self.insert = MagicMock()
        self.delete = MagicMock()
        self.get_children = MagicMock(return_value=[])
        self.item = MagicMock(return_value={'values': []})
        self.selection = MagicMock(return_value=[])
        self.place = MagicMock()
        self.cget = MagicMock(return_value='SystemButtonFace')
        self.title = MagicMock()
        self.geometry = MagicMock()
        self.set = MagicMock()

    def __getattr__(self, name):
        """Auto-create MagicMock for any tk attribute not explicitly defined."""
        if name == '_last_child_ids':
            return None
        m = MagicMock()
        object.__setattr__(self, name, m)
        return m

    def after(self, ms, func, *args):
        func(*args) if callable(func) else None

    def update_idletasks(self):
        pass

    def entryconfig(self, *args, **kw):
        pass


tk_patchers = [
    patch('tkinter.Frame', _RealishFrame),
    patch('tkinter.Tk', _RealishFrame),
    patch('tkinter.BOTH', 'both'),
    patch('tkinter.X', 'x'),
    patch('tkinter.Y', 'y'),
    patch('tkinter.LEFT', 'left'),
    patch('tkinter.RIGHT', 'right'),
    patch('tkinter.TOP', 'top'),
    patch('tkinter.BOTTOM', 'bottom'),
    patch('tkinter.NONE', 'none'),
    patch('tkinter.DISABLED', 'disabled'),
    patch('tkinter.NORMAL', 'normal'),
    patch('tkinter.END', 'end'),
    patch('tkinter.W', 'w'),
    patch('tkinter.StringVar'),
    patch('tkinter.BooleanVar'),
    patch('tkinter.IntVar'),
    patch('tkinter.Label'),
    patch('tkinter.Checkbutton'),
    patch('tkinter.Menu', _Realish),
    patch('tkinter.Canvas', _Realish),
    # Patch scrolledtext ASAP — full_app.py imports it
    patch('tkinter.scrolledtext.ScrolledText', _RealishFrame),
]
for p in tk_patchers:
    p.start()

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Patch filedialog and messagebox directly — they're constants imported by full_app.py
filedialog.asksaveasfilename = MagicMock(return_value="/tmp/test.log")
filedialog.askopenfilename = MagicMock(return_value="")
filedialog.asksaveasfilename = MagicMock(return_value="")
messagebox.showwarning = MagicMock()
messagebox.askyesno = MagicMock(return_value=False)

# Patch ttk
ttk.Frame = _RealishFrame
ttk.Label = _RealishFrame
ttk.Button = _RealishFrame
ttk.LabelFrame = _RealishFrame
ttk.PanedWindow = _RealishFrame
ttk.Notebook = _RealishFrame
ttk.Combobox = _RealishFrame
ttk.Checkbutton = _RealishFrame
ttk.Progressbar = _RealishFrame
ttk.Treeview = _RealishFrame  # Use same _RealishFrame for Treeview
ttk.Scrollbar = MagicMock

from utils.device_manager import DeviceInfo
from utils.aggregate_collector import AggregateResultCollector, AggregateReport, DeviceResultSummary, CommandSummary
from full_app import DeviceTableFrame, LogPanel, ConfigTab, DahuaConfigApp, AggregateReportTab, QueryTab


# ============================================================================
# Helpers
# ============================================================================

def make_device(ip="10.0.0.1", online=True, selected=False, status="在线", index=0):
    return DeviceInfo(
        index=index, ip=ip, port="80", username="admin",
        password='admin123',online=online, selected=selected,
        status=status, variables={},
    )


# ============================================================================
# DeviceTableFrame
# ============================================================================

class TestDeviceTableFrame:
    def test_init(self):
        parent = _RealishFrame()
        frame = DeviceTableFrame(parent)
        assert frame.devices == []

    def test_load_devices(self):
        parent = _RealishFrame()
        frame = DeviceTableFrame(parent)
        frame.tree = MagicMock()
        devices = [make_device(index=0), make_device(index=1)]
        frame.load_devices(devices)
        assert len(frame.devices) == 2

    def test_get_selected_devices(self):
        parent = _RealishFrame()
        frame = DeviceTableFrame(parent)
        d1 = make_device(selected=True, index=0)
        d2 = make_device(selected=False, index=1)
        frame.devices = [d1, d2]
        selected = frame.get_selected_devices()
        assert selected == [d1]

    def test_select_all(self):
        parent = _RealishFrame()
        frame = DeviceTableFrame(parent)
        d1 = make_device(selected=False, index=0)
        d2 = make_device(selected=False, index=1)
        frame.devices = [d1, d2]
        with patch.object(frame, 'load_devices'):
            frame.select_all()
            assert d1.selected is True
            assert d2.selected is True

    def test_select_none(self):
        parent = _RealishFrame()
        frame = DeviceTableFrame(parent)
        d1 = make_device(selected=True, index=0)
        d2 = make_device(selected=True, index=1)
        frame.devices = [d1, d2]
        with patch.object(frame, 'load_devices'):
            frame.select_none()
            assert d1.selected is False
            assert d2.selected is False

    def test_select_online(self):
        parent = _RealishFrame()
        frame = DeviceTableFrame(parent)
        d1 = make_device(online=True, index=0)
        d2 = make_device(online=False, index=1)
        frame.devices = [d1, d2]
        with patch.object(frame, 'load_devices'):
            frame.select_online()
            assert d1.selected is True
            assert d2.selected is False

    def test_update_device_status(self):
        parent = _RealishFrame()
        frame = DeviceTableFrame(parent)
        dev = make_device(index=0)
        frame.devices = [dev]
        frame._item_by_index = {0: MagicMock()}
        frame.tree = MagicMock()
        # tree.item(iid, option) → tree.item(*args) → use side_effect
        # ttk.Treeview.item(iid, option=None) returns the list for that option
        expected_vals = ["✓", "1", "10.0.0.1", "80", "在线", "", 0]
        frame.tree.item.side_effect = lambda *args, **kw: expected_vals
        frame.update_device_status(0, "配置完成", online=True, message="OK")
        assert dev.status == "配置完成"
        assert dev.last_message == "OK"

    def test_update_stats(self):
        parent = _RealishFrame()
        frame = DeviceTableFrame(parent)
        frame.stats_label = MagicMock()
        frame.devices = [
            make_device(online=True, selected=True, index=0),
            make_device(online=False, selected=False, index=1),
        ]
        frame.update_stats()
        frame.stats_label.config.assert_called_with(text="设备:2 在线:1 选中:1")


# ============================================================================
# LogPanel
# ============================================================================

class TestLogPanel:
    def test_init(self):
        parent = _RealishFrame()
        panel = LogPanel(parent)
        assert panel.text is not None

    def test_log(self):
        parent = _RealishFrame()
        panel = LogPanel(parent)
        panel.text = MagicMock()
        panel.log("test", "INFO")
        panel.text.insert.assert_called()
        panel.text.see.assert_called()

    def test_clear(self):
        parent = _RealishFrame()
        panel = LogPanel(parent)
        panel.text = MagicMock()
        panel.clear()
        panel.text.delete.assert_called_with('1.0', tk.END)

    def test_save_no_file(self):
        parent = _RealishFrame()
        panel = LogPanel(parent)
        panel.text = MagicMock()
        panel.text.get.return_value = "test log content"
        saved = getattr(filedialog, 'asksaveasfilename', MagicMock())
        saved.return_value = None
        with patch.object(builtins, 'open', MagicMock()):
            panel.save()


# ============================================================================
# ConfigTab
# ============================================================================

class TestConfigTab:
    def test_init(self):
        parent = _RealishFrame()
        config = {"timeout": 30, "config_concurrent": 80, "cgi_commands": ["T=1"]}
        tab = ConfigTab(parent, config)
        assert tab.config["timeout"] == 30

    def test_save_ui_to_config(self):
        config = {"cgi_commands": ["Cmd=1"], "timeout": 30}
        save_cb = MagicMock()
        parent = _RealishFrame()
        tab = ConfigTab(parent, config, save_callback=save_cb)

        tab.cmds_text = MagicMock()
        tab.cmds_text.get.return_value = "CmdA=1\nCmdB=2\n"

        for attr, val in [("timeout_var", "60"), ("concurrent_var", "50"),
                          ("ping_timeout_var", "5"), ("ping_concurrent_var", "100"),
                          ("auth_method_var", "basic"), ("exec_strategy_var", "command_first"),
                          ("enable_precheck_var", True), ("auto_skip_offline_var", False),
                          ("verify_ssl_var", True)]:
            v = MagicMock()
            v.get.return_value = val if isinstance(val, str) else val
            setattr(tab, attr, v)

        tab.save_ui_to_config()
        assert tab.config["cgi_commands"] == ["CmdA=1", "CmdB=2"]
        assert tab.config["timeout"] == 60
        assert tab.config["auth_method"] == "basic"
        assert tab.config["exec_strategy"] == "command_first"
        save_cb.assert_called_once()

    def test_load_config_to_ui(self):
        parent = _RealishFrame()
        config = {"cgi_commands": ["A=1", "B=2"], "timeout": 99}
        tab = ConfigTab(parent, config)
        tab.cmds_text = MagicMock()
        tab.timeout_var = MagicMock()

        tab.load_config_to_ui()
        tab.cmds_text.delete.assert_called_once()
        tab.cmds_text.insert.assert_called_with('1.0', 'A=1\nB=2')


# ============================================================================
# DahuaConfigApp — Core methods
# ============================================================================

class TestDahuaConfigApp:
    def test_init(self):
        app = DahuaConfigApp()
        assert app.config_data is not None
        assert app.log_manager is not None
        assert app.device_loader is not None
        assert app.detector is not None

    def test_log_message(self):
        app = DahuaConfigApp()
        app.log_message("test msg", "INFO")

    def test_save_config_success(self):
        app = DahuaConfigApp()
        with patch('full_app.ConfigManager.save_config', return_value=True):
            app.save_config({"timeout": 42})

    def test_save_config_failure(self):
        app = DahuaConfigApp()
        with patch('full_app.ConfigManager.save_config', return_value=False):
            app.save_config({"timeout": 42})

    def test_load_excel_no_file(self):
        app = DahuaConfigApp()
        filedialog.askopenfilename.return_value = None
        app.load_excel()

    def test_load_excel_with_file(self):
        app = DahuaConfigApp()
        filedialog.askopenfilename.return_value = "/tmp/test.xlsx"
        app.device_loader.load_from_excel = MagicMock(return_value=([make_device(index=0)], 1))
        app.load_excel()

    def test_start_detection_no_devices(self):
        app = DahuaConfigApp()
        app.device_table.devices = []
        app.start_detection()
        messagebox.showwarning.assert_called()

    def test_start_configuration_no_devices(self):
        app = DahuaConfigApp()
        app.device_table.get_selected_devices = MagicMock(return_value=[])
        app.start_configuration()
        messagebox.showwarning.assert_called()

    def test_stop_configuration(self):
        app = DahuaConfigApp()
        executor_mock = MagicMock()
        app.executor = executor_mock
        app.stop_configuration()
        executor_mock.stop.assert_called_once()

    def test_reload_config(self):
        app = DahuaConfigApp()
        mock_config = {"timeout": 42, "cgi_commands": []}
        with patch('full_app.ConfigManager.load_config', return_value=mock_config):
            app.reload_config()
            assert app.config_data["timeout"] == 42

    def test_reset_to_default_declined(self):
        app = DahuaConfigApp()
        messagebox.askyesno.return_value = False
        before = id(app.config_data)
        app.reset_to_default()
        assert id(app.config_data) == before  # unchanged

    def test_reset_to_default_confirmed(self):
        app = DahuaConfigApp()
        messagebox.askyesno.return_value = True
        mock_default = {"timeout": 0, "cgi_commands": []}
        with patch('full_app.ConfigManager.get_default_config', return_value=mock_default):
            app.reset_to_default()

    def test_export_devices_no_devices(self):
        app = DahuaConfigApp()
        app.device_table.devices = []
        app.export_devices()
        messagebox.showwarning.assert_called()

    def test_export_devices(self):
        app = DahuaConfigApp()
        app.device_table.devices = [make_device(index=0)]
        filedialog.asksaveasfilename.return_value = None
        app.export_devices()

    def test_import_devices(self):
        app = DahuaConfigApp()
        filedialog.askopenfilename.return_value = "/tmp/test.xlsx"
        app.import_devices()

    def test_open_log_directory(self):
        app = DahuaConfigApp()
        with patch.object(app.log_manager, 'open_log_directory', return_value=True):
            app.open_log_directory()

    def test_open_log_directory_fail(self):
        app = DahuaConfigApp()
        with patch.object(app.log_manager, 'open_log_directory', return_value=False):
            app.open_log_directory()

    def test_view_failure_logs(self):
        app = DahuaConfigApp()
        with patch.object(app.log_manager, 'open_failure_logs', return_value=True):
            app.view_failure_logs()

    def test_export_report_no_report(self):
        app = DahuaConfigApp()
        app.report_tab.report = None
        app.export_report()
        messagebox.showwarning.assert_called()

    def test_export_report_csv(self):
        app = DahuaConfigApp()
        report = AggregateReport(
            total_devices=2, online_devices=1, skipped_devices=1,
            total_commands=3, success_count=2, failed_count=1,
            success_rate=66.67, total_duration=10.5,
            per_device=[
                DeviceResultSummary(ip="10.0.0.1", port="80", status="成功", total_commands=2, success=2, failed=0, duration=5.0),
                DeviceResultSummary(ip="10.0.0.2", port="80", status="在线", total_commands=0, success=0, failed=0, duration=0.0),
            ],
            per_command={"__all_commands__": CommandSummary(command_name="__all_commands__", total_attempts=3, success=2, failed=1, avg_duration=3.5, failure_rate=33.33)},
            failure_details=[],
        )
        app.report_tab.report = report
        filedialog.asksaveasfilename.return_value = "/tmp/test_report.csv"
        with patch('builtins.open', MagicMock()), patch('csv.writer') as mock_writer:
            app.export_report()
        assert app.report_tab.report is report  # unchanged

    def test_export_report_cancelled(self):
        app = DahuaConfigApp()
        report = AggregateReport(total_devices=1, online_devices=1, per_device=[], per_command={}, failure_details=[])
        app.report_tab.report = report
        filedialog.asksaveasfilename.return_value = None
        app.export_report()  # just ensures no crash


# ============================================================================
# AggregateReportTab
# ============================================================================

class TestAggregateReportTab:
    def test_init(self):
        parent = _RealishFrame()
        tab = AggregateReportTab(parent)
        assert tab is not None

    def test_show_report(self):
        parent = _RealishFrame()
        tab = AggregateReportTab(parent)
        report = AggregateReport(
            total_devices=1, online_devices=1,
            total_commands=2, success_count=2, failed_count=0, success_rate=100.0,
            per_device=[DeviceResultSummary(ip="10.0.0.1", port="80", status="成功", total_commands=2, success=2, failed=0, duration=1.0)],
            per_command={},
            failure_details=[],
        )
        tab.text = MagicMock()
        tab.show_report(report)
        assert tab.report is report
        tab.text.delete.assert_called_once()
        tab.text.insert.assert_called_once()

    def test_clear_report(self):
        parent = _RealishFrame()
        tab = AggregateReportTab(parent)
        tab.report = AggregateReport(total_devices=1, per_device=[], per_command={}, failure_details=[])
        tab.text = MagicMock()
        tab.clear_report()
        assert tab.report is None
        tab.text.delete.assert_called_once()

    def test_show_report_with_backend(self):
        """Test show_report using real AggregateResultCollector.to_summary_text"""
        parent = _RealishFrame()
        tab = AggregateReportTab(parent)
        report = AggregateResultCollector.collect(
            results=[{"ip": "10.0.0.1", "port": "80", "success": True, "total_commands": 2, "success_commands": 2, "failed_commands": 0, "total_time": 1.0}],
            devices=[make_device(ip="10.0.0.1", online=True, index=0)],
            start_time=datetime.now(),
        )
        tab.text = MagicMock()
        tab.show_report(report)
        tab.text.delete.assert_called_once()
        assert tab.report.total_devices == 1
