#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DaHua_CGI Web UI — Flask Application

设备管理/配置执行/聚合报表/日志查看 一站式 Web 界面
"""

import json
import os
import sys
import threading
import time
from datetime import datetime
from io import StringIO
from typing import Dict, List, Optional

import pandas as pd
from flask import Flask, jsonify, render_template, request, send_file, Response

# 将项目根目录加入 sys.path 以便导入 src/utils/
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from utils.config_manager import ConfigManager
from utils.log_manager import LogManager
from utils.device_manager import DeviceLoader, DeviceDetector, ConfigExecutor
from utils.aggregate_collector import AggregateResultCollector

# ============================================================================
# 应用初始化
# ============================================================================

app = Flask(__name__)
app.secret_key = os.urandom(24)

# 全局状态
_config = ConfigManager.load_config()
_log_manager = LogManager(log_level=_config.get("log_level", "INFO"))
_device_loader = DeviceLoader(_log_manager)
_detector: Optional[DeviceDetector] = None
_executor: Optional[ConfigExecutor] = None
_executor_thread: Optional[threading.Thread] = None
_executor_start_time: Optional[datetime] = None
_executor_results: List[dict] = []
_aggregate_report: Optional[dict] = None
_execution_running = False
_execution_completed = False
_progress_data: Dict = {"percent": 0, "message": "", "stats": {}}
_log_buffer: List[Dict] = []
_selected_commands: List[str] = []


def _web_log_callback(message: str, level: str = "INFO") -> None:
    """Web 日志回调 — 缓冲到内存列表"""
    global _log_buffer
    _log_buffer.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "level": level,
        "message": message,
    })
    if len(_log_buffer) > 500:
        _log_buffer = _log_buffer[-300:]


def _web_progress_callback(phase: str, percent: float, stats: dict) -> None:
    """Web 进度回调"""
    global _progress_data
    _progress_data = {
        "phase": phase,
        "percent": round(percent, 1),
        "stats": stats,
    }


def _web_stop_callback() -> bool:
    """Web 停止回调 — 检查是否请求停止"""
    return False  # 暂不支持停止


@app.before_request
def _ensure_initialized():
    """确保检测器和执行器初始化"""
    global _detector, _executor, _config
    _config = ConfigManager.load_config()
    if _detector is None:
        _detector = DeviceDetector(_config, _log_manager, log_callback=_web_log_callback)
    if _executor is None:
        _executor = ConfigExecutor(_config, _log_manager, log_callback=_web_log_callback, use_async=False)


# ============================================================================
# 路由 — 页面
# ============================================================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/devices")
def page_devices():
    return render_template("devices.html")


@app.route("/config")
def page_config():
    return render_template("config.html")


@app.route("/reports")
def page_reports():
    return render_template("reports.html")


@app.route("/logs")
def page_logs():
    return render_template("logs.html")


# ============================================================================
# 路由 — API: 设备管理
# ============================================================================

@app.route("/api/devices", methods=["GET"])
def api_get_devices():
    """获取当前设备列表"""
    devices = _device_loader.devices
    result = []
    for d in devices:
        result.append({
            "index": d.index,
            "ip": d.ip,
            "port": d.port,
            "username": d.username,
            "status": d.status,
            "online": d.online,
            "selected": d.selected,
            "last_message": d.last_message,
            "display": d.get_display_info(),
            "variables": d.variables,
            "result": d.result,
        })
    return jsonify({"devices": result, "count": len(result), "source": _device_loader.excel_source_file})


@app.route("/api/devices/upload", methods=["POST"])
def api_upload_devices():
    """上传 Excel 加载设备"""
    global _execution_completed, _execution_running, _executor_results, _aggregate_report, _progress_data

    if "file" not in request.files:
        return jsonify({"error": "未上传文件"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "文件名为空"}), 400

    # 保存上传文件
    upload_dir = os.path.join(_project_root, "src", "web", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, file.filename)
    file.save(filepath)

    try:
        # 重置执行状态
        _execution_completed = False
        _execution_running = False
        _executor_results = []
        _aggregate_report = None
        _progress_data = {"percent": 0, "message": "", "stats": {}}

        devices, count = _device_loader.load_from_excel(filepath)
        return jsonify({"success": True, "devices_count": count, "source": filepath})
    except Exception as e:
        return jsonify({"error": f"加载失败: {str(e)}"}), 500


@app.route("/api/devices/select", methods=["POST"])
def api_select_devices():
    """设备选择控制"""
    data = request.json or {}
    mode = data.get("mode", "all")  # all | none | online | invert
    devices = _device_loader.devices
    if mode == "all":
        for d in devices:
            d.selected = True
    elif mode == "none":
        for d in devices:
            d.selected = False
    elif mode == "online":
        for d in devices:
            d.selected = d.online
    elif mode == "invert":
        for d in devices:
            d.selected = not d.selected
    elif mode == "toggle":
        idx = data.get("index")
        if idx is not None and 0 <= idx < len(devices):
            devices[idx].selected = not devices[idx].selected
    return jsonify({"success": True})


@app.route("/api/devices/ping", methods=["POST"])
def api_ping_devices():
    """Ping 检测设备"""
    global _detector, _progress_data
    if not _device_loader.devices:
        return jsonify({"error": "没有设备，请先上传 Excel"}), 400

    data = request.json or {}
    selected_only = data.get("selected_only", True)

    devices = _device_loader.devices
    if selected_only:
        devices = [d for d in devices if d.selected]

    if not devices:
        return jsonify({"error": "没有选中的设备"}), 400

    _web_log_callback(f"开始 Ping 检测 {len(devices)} 台设备...", "INFO")

    def run_ping():
        global _progress_data
        _detector.detect_devices(
            devices,
            progress_callback=_web_progress_callback,
            stop_callback=_web_stop_callback,
        )
        _web_log_callback("Ping 检测完成", "INFO")

    thread = threading.Thread(target=run_ping, daemon=True)
    thread.start()

    return jsonify({
        "success": True,
        "message": f"开始检测 {len(devices)} 台设备",
    })


@app.route("/api/devices/status")
def api_devices_status():
    """获取当前设备状态和进度"""
    return jsonify({
        "progress": _progress_data,
        "devices_count": len(_device_loader.devices),
        "execution_running": _execution_running,
        "execution_completed": _execution_completed,
    })


# ============================================================================
# 路由 — API: 配置执行
# ============================================================================

@app.route("/api/commands", methods=["GET"])
def api_get_commands():
    """获取可用 CGI 命令列表"""
    commands = _config.get("cgi_commands", [])
    result = []
    for cmd in commands:
        result.append({
            "name": cmd.get("name", ""),
            "description": cmd.get("description", ""),
            "path": cmd.get("path", ""),
            "method": cmd.get("method", "GET"),
            "auth": cmd.get("auth", "digest"),
            "timeout": cmd.get("timeout", 30),
            "params": cmd.get("params", []),
        })
    return jsonify({"commands": result})


@app.route("/api/execute/start", methods=["POST"])
def api_execute_start():
    """开始执行配置"""
    global _executor, _executor_thread, _executor_start_time, _executor_results
    global _execution_running, _execution_completed, _aggregate_report, _progress_data

    if _execution_running:
        return jsonify({"error": "执行正在进行中"}), 400

    if not _device_loader.devices:
        return jsonify({"error": "没有设备，请先上传 Excel"}), 400

    data = request.json or {}
    selected_only = data.get("selected_only", True)
    strategy = data.get("strategy", _config.get("exec_strategy", "device_first"))
    command_names = data.get("commands", [])

    devices = _device_loader.devices
    if selected_only:
        devices = [d for d in devices if d.selected]

    if not devices:
        return jsonify({"error": "没有选中的设备"}), 400

    # 过滤命令
    all_commands = _config.get("cgi_commands", [])
    if command_names:
        filtered_commands = [c for c in all_commands if c.get("name") in command_names]
    else:
        filtered_commands = all_commands

    if not filtered_commands:
        return jsonify({"error": "没有选择的命令"}), 400

    # 重置状态
    _execution_running = True
    _execution_completed = False
    _executor_results = []
    _aggregate_report = None
    _progress_data = {"percent": 0, "message": "开始执行...", "stats": {}}
    _executor_start_time = datetime.now()

    _web_log_callback(
        f"开始执行: {len(devices)} 台设备 × {len(filtered_commands)} 条命令, 策略: {strategy}",
        "INFO"
    )

    # 在线检查 & 标记设备
    # 注意：通过 ping 在线检测过的设备才有 online 状态。如果没有 ping 过，强制所有选中设备为 "在线"
    for d in devices:
        if not d.online:
            d.online = True
            d.status = "等待配置"

    def run_execute():
        global _executor, _executor_results, _execution_running, _execution_completed, _aggregate_report

        try:
            # 重新创建执行器
            _executor = ConfigExecutor(
                _config, _log_manager,
                log_callback=_web_log_callback,
                use_async=False,
            )

            # 设置配置中的命令为过滤后的命令
            old_commands = _config.get("cgi_commands", [])
            _config["cgi_commands"] = filtered_commands

            _executor_results = _executor.execute_batch(
                devices=devices,
                mode="standard",
                exec_strategy=strategy,
                progress_callback=_web_progress_callback,
                stop_callback=_web_stop_callback,
            )

            # 恢复原命令列表
            _config["cgi_commands"] = old_commands

            # 聚合报表
            collector = AggregateResultCollector()
            report = collector.collect(
                _executor_results,
                devices,
                start_time=_executor_start_time,
            )
            _aggregate_report = collector.to_dict(report)

            _web_log_callback(
                f"执行完成: {report.success_count} 成功 / {report.failed_count} 失败, "
                f"成功率 {report.success_rate:.1f}%",
                "INFO"
            )
        except Exception as e:
            _web_log_callback(f"执行异常: {str(e)}", "ERROR")
        finally:
            _execution_running = False
            _execution_completed = True
            _progress_data["percent"] = 100

    _executor_thread = threading.Thread(target=run_execute, daemon=True)
    _executor_thread.start()

    return jsonify({
        "success": True,
        "message": f"开始执行: {len(devices)} 台设备 × {len(filtered_commands)} 条命令",
        "devices_count": len(devices),
        "commands_count": len(filtered_commands),
    })


@app.route("/api/execute/status")
def api_execute_status():
    """获取执行状态和进度"""
    return jsonify({
        "running": _execution_running,
        "completed": _execution_completed,
        "progress": _progress_data,
        "results_count": len(_executor_results),
    })


@app.route("/api/execute/results")
def api_execute_results():
    """获取执行结果"""
    if not _execution_completed and _execution_running:
        return jsonify({"error": "执行尚未完成", "running": True, "progress": _progress_data}), 200
    return jsonify({
        "results": _executor_results,
        "report": _aggregate_report,
        "completed": _execution_completed,
    })


# ============================================================================
# 路由 — API: 配置管理
# ============================================================================

@app.route("/api/config", methods=["GET"])
def api_get_config():
    """获取当前配置"""
    return jsonify({"config": _config})


@app.route("/api/config", methods=["POST"])
def api_save_config():
    """保存配置"""
    data = request.json or {}
    if "config" not in data:
        return jsonify({"error": "缺少配置数据"}), 400

    global _config
    new_config = data["config"]
    try:
        # 合并配置（仅保留非 cgi_commands 字段以避免覆盖命令定义）
        existing = _config.copy()
        for k, v in new_config.items():
            if k != "cgi_commands":
                existing[k] = v
        ok = ConfigManager.save_config(existing)
        if ok:
            _config = ConfigManager.load_config()  # 重新加载
            return jsonify({"success": True, "message": "配置已保存"})
        else:
            return jsonify({"error": "保存配置失败"}), 500
    except Exception as e:
        return jsonify({"error": f"保存异常: {str(e)}"}), 500


# ============================================================================
# 路由 — API: 日志
# ============================================================================

@app.route("/api/logs")
def api_get_logs():
    """获取日志（内存缓冲 + 日志文件）"""
    # 内存日志
    log_type = request.args.get("type", "buffer")
    lines_count = int(request.args.get("lines", 200))

    if log_type == "buffer":
        return jsonify({"logs": _log_buffer[-lines_count:]})
    elif log_type == "detailed":
        # 从详细日志文件读取
        log_file = _log_manager.detailed_log_file
        return _read_log_file(log_file, lines_count)
    elif log_type == "failure":
        log_file = _log_manager.failure_log_file
        return _read_log_file(log_file, lines_count)
    else:
        return jsonify({"logs": _log_buffer[-lines_count:]})


@app.route("/api/logs/clear", methods=["POST"])
def api_clear_logs():
    """清空内存日志"""
    global _log_buffer
    _log_buffer = []
    return jsonify({"success": True})


# ============================================================================
# 路由 — API: 导出报表
# ============================================================================

@app.route("/api/reports/export")
def api_export_report():
    """导出报表"""
    if not _aggregate_report:
        return jsonify({"error": "没有报表数据，请先执行配置"}), 400

    fmt = request.args.get("format", "csv")

    if fmt == "json":
        return Response(
            json.dumps(_aggregate_report, ensure_ascii=False, indent=2),
            mimetype="application/json",
            headers={"Content-Disposition": "attachment; filename=report.json"},
        )
    elif fmt == "csv":
        # 设备维度 CSV
        output = StringIO()
        df = pd.DataFrame(_aggregate_report.get("设备维度", []))
        df.to_csv(output, index=False, encoding="utf-8-sig")
        return Response(
            output.getvalue(),
            mimetype="text/csv; charset=utf-8-sig",
            headers={"Content-Disposition": "attachment; filename=report.csv"},
        )
    else:
        # 纯文本摘要
        collector = AggregateResultCollector()
        from utils.aggregate_collector import AggregateReport
        report = AggregateReport()
        # 简版处理
        lines = []
        lines.append("=" * 56)
        lines.append("  DaHua_CGI 聚合报表")
        lines.append("=" * 56)
        overview = _aggregate_report.get("总览", {})
        for k, v in overview.items():
            lines.append(f"  {k}: {v}")
        lines.append("-" * 56)
        lines.append("  设备维度:")
        for d in _aggregate_report.get("设备维度", []):
            lines.append(f"    {d.get('IP','')}:{d.get('端口','')}  {d.get('状态','')}  [{d.get('成功',0)}/{d.get('失败',0)}]  {d.get('耗时(秒)',0)}s")
        lines.append("=" * 56)
        return Response(
            "\n".join(lines),
            mimetype="text/plain; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=report.txt"},
        )


# ============================================================================
# 辅助函数
# ============================================================================

def _read_log_file(filepath: Optional[str], lines_count: int = 200):
    """从日志文件读取最后 N 行"""
    if not filepath or not os.path.exists(filepath):
        return jsonify({"logs": [], "file": None})
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
        tail = all_lines[-lines_count:]
        return jsonify({
            "logs": [l.rstrip("\n") for l in tail],
            "file": filepath,
            "total_lines": len(all_lines),
        })
    except Exception as e:
        return jsonify({"logs": [f"读取日志失败: {e}"], "file": filepath})


# ============================================================================
# 入口
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  DaHua_CGI Web UI")
    print("=" * 60)
    print(f"  Config: {_config.get('exec_strategy', 'device_first')} / {_config.get('auth_method', 'digest')}")
    print(f"  Log level: {_config.get('log_level', 'INFO')}")
    print(f"  Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 60)
    print("  Open browser: http://127.0.0.1:5000")
    print("=" * 60)

    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
