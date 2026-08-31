#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DaHua_CGI Web UI — Flask Application

设备管理/配置执行/聚合报表/日志查看 一站式 Web 界面
"""

import json
import os
import re
import sys
import threading
import time
import ipaddress
from datetime import datetime
from io import BytesIO, StringIO
from typing import Dict, List, Optional

import pandas as pd
from flask import Flask, jsonify, render_template, request, send_file, Response

# 将项目根目录加入 sys.path 以便导入 src/utils/
_app_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.join(_app_dir, "..", "..")
_src_dir = os.path.join(_app_dir, "..")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from utils.config_manager import ConfigManager
from utils.cgi_reference_manager import CGIReferenceManager
from utils.log_manager import LogManager
from utils.device_manager import DeviceLoader, DeviceDetector, ConfigExecutor
from utils.device_manager import DeviceInfo
from utils.aggregate_collector import AggregateResultCollector
from utils.cgi_query import CgiQueryExecutor

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
_execution_stopped = False
_execution_stop_requested = False
_execution_device_ips: List[str] = []
_progress_data: Dict = {"percent": 0, "message": "", "stats": {}}
_log_buffer: List[Dict] = []
_selected_commands: List[str] = []
_device_state_file = os.path.join(_app_dir, "uploads", "device_state.json")

_CONFIG_PARAMETER_PATTERN = re.compile(
    r"^[A-Za-z][A-Za-z0-9_]*(?:\[\d+\])?(?:\.[A-Za-z][A-Za-z0-9_]*(?:\[\d+\])?)+$"
)

# CGI查询全局状态
_query_executor: Optional[CgiQueryExecutor] = None
_query_thread: Optional[threading.Thread] = None
_query_result_data: List[List[str]] = []
_query_result_columns: List[str] = []
_query_row_dicts: List[Dict[str, str]] = []
_query_running = False
_query_completed = False
_query_stopped = False
_query_stop_requested = False
_query_progress_data: Dict = {"percent": 0, "message": "", "stats": {}}


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
        "message": _progress_data.get("message", ""),
        "stats": stats,
    }


def _web_stop_callback() -> bool:
    """Web 停止回调 — 检查是否请求停止"""
    return _execution_stop_requested


def _reset_execution_state() -> None:
    """设备清单变动后清空与旧设备关联的执行结果。"""
    global _execution_completed, _execution_running, _execution_stopped, _execution_stop_requested
    global _executor_results, _aggregate_report, _progress_data
    _execution_completed = False
    _execution_running = False
    _execution_stopped = False
    _execution_stop_requested = False
    _execution_device_ips = []
    _executor_results = []
    _aggregate_report = None
    _progress_data = {"percent": 0, "message": "", "stats": {}}


def _reset_query_state() -> None:
    """清理查询执行状态。"""
    global _query_running, _query_completed, _query_stopped, _query_stop_requested
    global _query_result_data, _query_result_columns, _query_row_dicts, _query_progress_data
    _query_running = False
    _query_completed = False
    _query_stopped = False
    _query_stop_requested = False
    _query_result_data = []
    _query_result_columns = []
    _query_row_dicts = []
    _query_progress_data = {"percent": 0, "message": "", "stats": {}}


def _serialize_device_snapshot(device) -> dict:
    """将设备及其当前执行结果压缩为前端可用快照。"""
    result = device.result if isinstance(device.result, dict) else None
    result_summary = None
    if result:
        result_summary = {
            "ip": result.get("ip", device.ip),
            "port": result.get("port", device.port),
            "success": result.get("success", False),
            "total_commands": result.get("total_commands", 0),
            "success_commands": result.get("success_commands", 0),
            "failed_commands": result.get("failed_commands", 0),
            "failure_details": result.get("failure_details"),
            "start_time": result.get("start_time", ""),
            "end_time": result.get("end_time", ""),
            "total_time": result.get("total_time", 0),
        }

    return {
        "index": device.index,
        "ip": device.ip,
        "port": device.port,
        "username": device.username,
        "status": device.status,
        "online": device.online,
        "selected": device.selected,
        "last_message": device.last_message,
        "display": device.get_display_info(),
        "variables": getattr(device, "variables", {}),
        "config_variables": _get_device_config_variables(device),
        "result": result_summary,
    }


def _is_config_parameter_name(name: str) -> bool:
    """判断 Excel 额外列名是否像 Dahua setConfig 参数路径。"""
    return bool(_CONFIG_PARAMETER_PATTERN.match(str(name).strip()))


def _get_device_config_variables(device) -> Dict[str, str]:
    """返回可直接转换为 setConfig 命令的导入参数。"""
    variables = getattr(device, "variables", {}) or {}
    return {
        str(name).strip(): str(value).strip()
        for name, value in variables.items()
        if _is_config_parameter_name(str(name)) and str(value).strip()
    }


def _build_imported_config_commands(devices) -> List[str]:
    """把 Excel 参数列转换为参数占位命令，用于每台设备替换自己的值。"""
    commands = []
    seen = set()
    for device in devices:
        for parameter in _get_device_config_variables(device):
            if parameter in seen:
                continue
            seen.add(parameter)
            commands.append(f"{parameter}={{{parameter}}}")
    return commands


def _executed_device_snapshots() -> List[dict]:
    """返回本次执行涉及的设备快照（未选中执行的不返回）。"""
    return [
        _serialize_device_snapshot(device)
        for device in _device_loader.devices
        if device.ip in _execution_device_ips
    ]


def _serialize_device_for_state(device) -> dict:
    return {
        "index": device.index,
        "ip": device.ip,
        "port": device.port,
        "username": device.username,
        "password": device.password,
        "status": device.status,
        "online": device.online,
        "selected": device.selected,
        "variables": getattr(device, "variables", {}),
        "excel_row": getattr(device, "excel_row", 0),
        "last_message": device.last_message,
        "result": _serialize_device_snapshot(device)["result"],
    }


def _device_from_state(raw: dict, index: int) -> DeviceInfo:
    device = DeviceInfo(
        index=index,
        ip=str(raw.get("ip", "")).strip(),
        port=str(raw.get("port", "80")).strip() or "80",
        username=str(raw.get("username", "admin")).strip() or "admin",
        password=str(raw.get("password", "")),
        status=str(raw.get("status", "未检测")),
        online=bool(raw.get("online", False)),
        selected=bool(raw.get("selected", False)),
        variables=raw.get("variables", {}) or {},
        excel_row=int(raw.get("excel_row", 0) or 0),
        last_message=str(raw.get("last_message", "")),
    )
    result = raw.get("result")
    if isinstance(result, dict):
        device.result = result
    return device


def _save_device_state() -> None:
    os.makedirs(os.path.dirname(_device_state_file), exist_ok=True)
    payload = {
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "source": _device_loader.excel_source_file,
        "loaded_time": _device_loader.loaded_time.isoformat(timespec="seconds") if _device_loader.loaded_time else "",
        "devices": [_serialize_device_for_state(device) for device in _device_loader.devices],
    }
    with open(_device_state_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _clear_device_state() -> None:
    if os.path.exists(_device_state_file):
        os.remove(_device_state_file)


def _restore_device_state() -> None:
    if os.path.exists(_device_state_file):
        with open(_device_state_file, "r", encoding="utf-8") as f:
            payload = json.load(f)
        _device_loader.devices = [
            _device_from_state(raw, index)
            for index, raw in enumerate(payload.get("devices", []))
            if str(raw.get("ip", "")).strip()
        ]
        _device_loader.excel_source_file = payload.get("source", "")
        loaded_time = payload.get("loaded_time")
        if loaded_time:
            try:
                _device_loader.loaded_time = datetime.fromisoformat(loaded_time)
            except ValueError:
                _device_loader.loaded_time = datetime.now()
        return

    upload_dir = os.path.join(_app_dir, "uploads")
    if not os.path.isdir(upload_dir):
        return
    candidates = [
        os.path.join(upload_dir, name)
        for name in os.listdir(upload_dir)
        if name.lower().endswith((".xlsx", ".xls"))
    ]
    if not candidates:
        return
    latest = max(candidates, key=os.path.getmtime)
    try:
        _device_loader.load_from_excel(latest, mode="customized")
        _save_device_state()
        _web_log_callback(f"已从最近上传的设备文件恢复: {latest}", "INFO")
    except Exception as exc:
        _web_log_callback(f"恢复设备文件失败: {exc}", "WARNING")


def _normalize_device_payload(data: dict, current_index: Optional[int] = None) -> dict:
    """校验手动维护的设备字段，并返回标准化后的数据。"""
    ip = str(data.get("ip", "")).strip()
    port = str(data.get("port", "80")).strip() or "80"
    username = str(data.get("username", "admin")).strip() or "admin"
    password = str(data.get("password", ""))

    try:
        parsed_ip = ipaddress.ip_address(ip)
    except ValueError as exc:
        raise ValueError("IP 地址格式无效") from exc
    if parsed_ip.version != 4:
        raise ValueError("仅支持 IPv4 地址")

    try:
        port_number = int(port)
    except ValueError as exc:
        raise ValueError("端口必须是 1-65535 的整数") from exc
    if not 1 <= port_number <= 65535:
        raise ValueError("端口必须在 1-65535 之间")

    for device in _device_loader.devices:
        if device.ip == ip and device.index != current_index:
            raise ValueError(f"设备 IP 已存在: {ip}")

    return {
        "ip": ip,
        "port": str(port_number),
        "username": username,
        "password": password,
    }


def _command_name(command) -> str:
    """返回命令在 Web UI 中使用的唯一标识。"""
    if isinstance(command, dict):
        return str(command.get("name", ""))
    return str(command)


def _serialize_command(command: object) -> dict:
    """将新版字典命令和旧版 key=value 命令统一为 API 响应格式。"""
    if isinstance(command, dict):
        return {
            "name": _command_name(command),
            "description": command.get("description", ""),
            "path": command.get("path", ""),
            "method": command.get("method", "GET"),
            "auth": command.get("auth", "digest"),
            "timeout": command.get("timeout", 30),
            "params": command.get("params", []),
        }

    return {
        "name": _command_name(command),
        "description": "旧版 setConfig 配置项",
        "path": "/cgi-bin/configManager.cgi",
        "method": "GET",
        "auth": _config.get("auth_method", "digest"),
        "timeout": _config.get("timeout", 3000) / 1000,
        "params": [],
    }


_restore_device_state()


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
    result = [_serialize_device_snapshot(d) for d in devices]
    return jsonify({"devices": result, "count": len(result), "source": _device_loader.excel_source_file})


@app.route("/api/devices/upload", methods=["POST"])
def api_upload_devices():
    """上传 Excel 加载设备"""
    if "file" not in request.files:
        return jsonify({"error": "未上传文件"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "文件名为空"}), 400

    # 保存上传文件
    upload_dir = os.path.join(_app_dir, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, file.filename)
    file.save(filepath)

    try:
        _reset_execution_state()

        devices, count = _device_loader.load_from_excel(filepath, mode="customized")
        _save_device_state()
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
        else:
            return jsonify({"error": "设备不存在"}), 404
    else:
        return jsonify({"error": "不支持的选择操作"}), 400
    _save_device_state()
    return jsonify({"success": True})


@app.route("/api/devices/add", methods=["POST"])
def api_add_device():
    """手动添加单台设备，并默认选中。"""
    try:
        values = _normalize_device_payload(request.json or {})
        device = DeviceInfo(index=len(_device_loader.devices), selected=True, **values)
        _device_loader.devices.append(device)
        _device_loader.excel_source_file = ""
        _device_loader.loaded_time = datetime.now()
        _reset_execution_state()
        _save_device_state()
        return jsonify({
            "success": True,
            "device": {
                "index": device.index,
                "ip": device.ip,
                "port": device.port,
                "username": device.username,
            },
        }), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/devices/<int:index>", methods=["PATCH"])
def api_update_device(index: int):
    """编辑已添加或导入的设备。"""
    if not 0 <= index < len(_device_loader.devices):
        return jsonify({"error": "设备不存在"}), 404

    try:
        device = _device_loader.devices[index]
        payload = dict(request.json or {})
        if not str(payload.get("password", "")):
            payload["password"] = device.password
        values = _normalize_device_payload(payload, current_index=index)
        device.ip = values["ip"]
        device.port = values["port"]
        device.username = values["username"]
        device.password = values["password"]
        device.status = "未检测"
        device.online = False
        device.last_message = "设备信息已更新，建议重新 Ping 检测"
        _reset_execution_state()
        _save_device_state()
        return jsonify({"success": True})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/devices/clear", methods=["POST"])
def api_clear_devices():
    """清空所有已上传设备"""
    _device_loader.devices.clear()
    _device_loader.excel_source_file = ""
    _device_loader.loaded_time = None
    _reset_execution_state()
    _clear_device_state()
    return jsonify({"success": True})


@app.route("/api/devices/delete", methods=["POST"])
def api_delete_devices():
    """删除选中的设备"""
    data = request.json or {}
    indices = data.get("indices", [])
    if not indices:
        return jsonify({"error": "未指定要删除的设备"}), 400
    if not isinstance(indices, list):
        return jsonify({"error": "删除参数格式不正确"}), 400
    try:
        indices = [int(idx) for idx in indices]
    except (TypeError, ValueError):
        return jsonify({"error": "删除索引必须是整数"}), 400
    
    devices = _device_loader.devices
    # 从大到小排序，避免删除后索引偏移
    deleted = 0
    for idx in sorted(indices, reverse=True):
        if 0 <= idx < len(devices):
            devices.pop(idx)
            deleted += 1
    
    # 重新整理 index
    for i, d in enumerate(devices):
        d.index = i

    _reset_execution_state()
    if deleted == 0:
        return jsonify({"error": "没有删除任何设备"}), 400
    _save_device_state()
    return jsonify({"success": True, "deleted": deleted})


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
        _save_device_state()
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
        "execution_stopped": _execution_stopped,
    })


# ============================================================================
# 路由 — API: 配置执行
# ============================================================================

@app.route("/api/commands", methods=["GET"])
def api_get_commands():
    """获取可用 CGI 命令列表"""
    commands = _config.get("cgi_commands", [])
    return jsonify({"commands": [_serialize_command(cmd) for cmd in commands]})


@app.route("/api/cgi-library", methods=["GET"])
def api_get_cgi_library():
    """返回可直接选择的实测查询和配置 CGI 范本。"""
    return jsonify({
        "query_templates": CGIReferenceManager.get_query_library(),
        "set_options": CGIReferenceManager.get_setconfig_library(),
    })


@app.route("/api/execute/start", methods=["POST"])
def api_execute_start():
    """开始执行配置"""
    global _executor, _executor_thread, _executor_start_time, _executor_results
    global _execution_running, _execution_completed, _execution_stopped, _execution_stop_requested
    global _execution_device_ips
    global _aggregate_report, _progress_data

    if _execution_running:
        return jsonify({"error": "执行正在进行中"}), 400

    if not _device_loader.devices:
        return jsonify({"error": "没有设备，请先上传 Excel"}), 400

    data = request.json or {}
    strategy = data.get("strategy", _config.get("exec_strategy", "device_first"))
    command_names = data.get("commands")
    if command_names is not None and not isinstance(command_names, list):
        return jsonify({"error": "命令选择格式不正确"}), 400
    custom_commands = data.get("custom_commands", [])
    if not isinstance(custom_commands, list) or not all(isinstance(command, str) for command in custom_commands):
        return jsonify({"error": "自定义命令格式不正确"}), 400
    custom_commands = [command.strip() for command in custom_commands if command.strip()]
    use_imported_params = bool(data.get("use_imported_params", False))

    devices = [device for device in _device_loader.devices if device.selected]

    if not devices:
        return jsonify({"error": "请先在设备管理页选择设备"}), 400

    _execution_device_ips = [device.ip for device in devices]

    # 过滤命令
    all_commands = _config.get("cgi_commands", [])
    if command_names is None:
        filtered_commands = all_commands
    elif command_names:
        filtered_commands = [
            command for command in all_commands
            if _command_name(command) in command_names
        ]
    else:
        filtered_commands = []

    if use_imported_params:
        imported_commands = _build_imported_config_commands(devices)
        custom_commands = custom_commands + [
            command for command in imported_commands
            if command not in custom_commands
        ]

    filtered_commands = filtered_commands + custom_commands

    if not filtered_commands:
        if use_imported_params:
            return jsonify({"error": "选中设备没有可执行的导入参数列"}), 400
        return jsonify({"error": "没有选择的命令"}), 400

    execution_mode = data.get("mode")
    if execution_mode not in ("standard", "customized"):
        has_placeholders = any(re.search(r"\{([^}]+)\}", command) for command in filtered_commands)
        execution_mode = "customized" if has_placeholders or use_imported_params else "standard"

    # 重置状态
    _execution_running = True
    _execution_completed = False
    _execution_stopped = False
    _execution_stop_requested = False
    _executor_results = []
    _aggregate_report = None
    _progress_data = {"percent": 0, "message": "开始执行...", "stats": {}}
    _executor_start_time = datetime.now()

    _web_log_callback(
        f"开始执行: {len(devices)} 台设备 × {len(filtered_commands)} 条命令, 策略: {strategy}, 模式: {execution_mode}",
        "INFO"
    )

    # 在线检查 & 标记设备
    # 注意：通过 ping 在线检测过的设备才有 online 状态。如果没有 ping 过，强制所有选中设备为 "在线"
    for d in devices:
        if not d.online:
            d.online = True
            d.status = "等待配置"

    def run_execute():
        global _executor, _executor_results, _execution_running, _execution_completed
        global _execution_stopped, _aggregate_report, _progress_data
        old_commands = _config.get("cgi_commands", [])

        try:
            # 重新创建执行器
            _executor = ConfigExecutor(
                _config, _log_manager,
                log_callback=_web_log_callback,
                use_async=False,
            )

            # 设置配置中的命令为过滤后的命令
            _config["cgi_commands"] = filtered_commands

            _executor_results = _executor.execute_batch(
                devices=devices,
                mode=execution_mode,
                exec_strategy=strategy,
                progress_callback=_web_progress_callback,
                stop_callback=_web_stop_callback,
            )

            if _execution_stop_requested:
                _execution_stopped = True
                _progress_data["message"] = "已停止"
                _web_log_callback("配置执行已被用户停止", "WARNING")

            # 聚合报表
            collector = AggregateResultCollector()
            report = collector.collect(
                _executor_results,
                devices,
                start_time=_executor_start_time,
            )
            _aggregate_report = collector.to_dict(report)

            if not _execution_stopped:
                _web_log_callback(
                    f"执行完成: {report.success_count} 成功 / {report.failed_count} 失败, "
                    f"成功率 {report.success_rate:.1f}%",
                    "INFO"
                )
        except Exception as e:
            _web_log_callback(f"执行异常: {str(e)}", "ERROR")
        finally:
            _config["cgi_commands"] = old_commands
            _execution_running = False
            _execution_completed = True
            if _execution_stopped:
                _progress_data["message"] = "已停止"
            else:
                _progress_data["percent"] = 100
            _save_device_state()

    _executor_thread = threading.Thread(target=run_execute, daemon=True)
    _executor_thread.start()

    return jsonify({
        "success": True,
        "message": f"开始执行: {len(devices)} 台设备 × {len(filtered_commands)} 条命令",
        "devices_count": len(devices),
        "commands_count": len(filtered_commands),
        "imported_commands_count": len(_build_imported_config_commands(devices)) if use_imported_params else 0,
    })


@app.route("/api/execute/status")
def api_execute_status():
    """获取执行状态和进度"""
    return jsonify({
        "running": _execution_running,
        "completed": _execution_completed,
        "stopped": _execution_stopped,
        "stop_requested": _execution_stop_requested,
        "progress": _progress_data,
        "results_count": len(_executor_results),
        "devices": _executed_device_snapshots(),
    })


@app.route("/api/execute/stop", methods=["POST"])
def api_execute_stop():
    """停止正在执行的配置任务。"""
    global _execution_stop_requested, _progress_data

    if not _execution_running:
        return jsonify({
            "success": True,
            "message": "当前没有正在执行的配置任务",
            "running": False,
            "stopped": _execution_stopped,
        })

    _execution_stop_requested = True
    _progress_data["message"] = "正在停止..."
    _web_log_callback("收到配置停止请求", "WARNING")
    if _executor is not None:
        try:
            _executor.stop()
        except Exception as exc:
            _web_log_callback(f"停止配置执行器异常: {exc}", "ERROR")

    return jsonify({"success": True, "message": "已请求停止配置执行"})


@app.route("/api/execute/results")
def api_execute_results():
    """获取执行结果"""
    if not _execution_completed and _execution_running:
        return jsonify({
            "error": "执行尚未完成",
            "running": True,
            "progress": _progress_data,
            "devices": _executed_device_snapshots(),
        }), 200
    return jsonify({
        "results": _executor_results,
        "report": _aggregate_report,
        "completed": _execution_completed,
        "stopped": _execution_stopped,
        "devices": _executed_device_snapshots(),
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
# 路由 — Excel模板下载
# ============================================================================

@app.route("/api/template/download")
def api_template_download():
    """下载Excel导入模板"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    required_headers = ["IP地址", "端口", "用户名", "密码"]
    osd_headers = [
        "VideoWidget[0].CustomTitle[1].Text",
        "VideoWidget[0].CustomTitle[1].EncodeBlend",
        "VideoWidget[0].CustomTitle[1].PreviewBlend",
        "VideoWidget[0].CustomTitle[1].TextAlign",
    ]
    headers = required_headers + osd_headers

    wb = Workbook()
    ws = wb.active
    ws.title = "设备导入"
    ws.append(headers)
    ws.append([
        "192.168.1.10",
        "80",
        "admin",
        "password",
        "一号门",
        "true",
        "true",
        "2",
    ])

    ws2 = wb.create_sheet("说明")
    ws2.append(["规则", "内容"])
    ws2.append(["前4列", "必须保持为 IP地址 / 端口 / 用户名 / 密码"])
    ws2.append(["参数列", "第5列起可填写要写入的 Dahua setConfig 参数名"])
    ws2.append(["执行", "导入后在配置页勾选 使用导入参数 即可按每行值批量写入"])

    header_fill = PatternFill("solid", fgColor="1f6feb")
    header_font = Font(color="FFFFFF", bold=True)
    for sheet in (ws, ws2):
        for cell in sheet[1]:
            cell.fill = header_fill
            cell.font = header_font
        for column in sheet.columns:
            width = max(len(str(cell.value or "")) for cell in column) + 2
            sheet.column_dimensions[get_column_letter(column[0].column)].width = min(max(width, 12), 48)

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="device_import_template.xlsx",
    )


# ============================================================================
# 路由 — CGI查询
# ============================================================================

@app.route("/query")
def page_query():
    """CGI批量查询页面"""
    return render_template("query.html")


@app.route("/api/query/execute", methods=["POST"])
def api_query_execute():
    """执行CGI查询"""
    global _query_executor, _query_thread, _query_result_data, _query_result_columns, _query_row_dicts, _config
    global _query_running, _query_completed, _query_stopped, _query_stop_requested, _query_progress_data

    if _query_running:
        return jsonify({"error": "查询正在进行中"}), 400

    data = request.json or {}
    commands = data.get("commands", [])

    if not commands:
        return jsonify({"error": "请至少输入一个查询命令"}), 400

    devices = [device for device in _device_loader.devices if device.selected]

    if not devices:
        return jsonify({"error": "请先在设备管理页选择设备"}), 400

    _query_executor = CgiQueryExecutor(_config, _log_manager, log_callback=_web_log_callback)
    _query_result_data = []
    _query_result_columns = []
    _query_row_dicts = []
    _query_running = True
    _query_completed = False
    _query_stopped = False
    _query_stop_requested = False
    _query_progress_data = {
        "percent": 0,
        "message": "开始查询...",
        "stats": {"completed": 0, "total": len(devices)},
    }

    def query_progress(progress: float) -> None:
        global _query_progress_data
        completed = int(round((progress / 100) * len(devices))) if devices else 0
        _query_progress_data = {
            "percent": round(progress, 1),
            "message": "查询中...",
            "stats": {"completed": completed, "total": len(devices)},
        }

    def query_should_stop() -> bool:
        return _query_stop_requested

    def query_row_callback(row_data: dict, columns: List[str]) -> None:
        global _query_result_data, _query_result_columns, _query_row_dicts
        _query_result_columns = columns
        normalized = {col: str(row_data.get(col, "")) for col in columns}
        _query_row_dicts.append(normalized)
        _query_result_data = [[row.get(col, "") for col in columns] for row in _query_row_dicts]

    def run_query() -> None:
        global _query_result_data, _query_result_columns, _query_row_dicts
        global _query_running, _query_completed, _query_stopped, _query_progress_data
        try:
            df = _query_executor.execute_query(
                devices,
                commands,
                progress_callback=query_progress,
                stop_callback=query_should_stop,
                row_callback=query_row_callback,
            )
            _query_result_columns = list(df.columns)
            _query_result_data = []
            _query_row_dicts = []
            for _, row in df.iterrows():
                row_dict = {col: (str(row[col]) if pd.notna(row[col]) else "") for col in df.columns}
                _query_row_dicts.append(row_dict)
                _query_result_data.append([row_dict[col] for col in df.columns])

            if _query_stop_requested or (_query_executor and _query_executor.is_stopped()):
                _query_stopped = True
                _query_progress_data["message"] = "已停止"
                _web_log_callback(f"查询已停止，已返回 {len(_query_result_data)} 台设备结果", "WARNING")
            else:
                _query_progress_data["percent"] = 100
                _query_progress_data["message"] = "查询完成"
                _web_log_callback(f"查询完成: {len(_query_result_data)} 台设备", "INFO")
        except Exception as e:
            _query_progress_data["message"] = f"查询失败: {str(e)}"
            _web_log_callback(f"查询失败: {str(e)}", "ERROR")
        finally:
            _query_running = False
            _query_completed = True

    _query_thread = threading.Thread(target=run_query, daemon=True)
    _query_thread.start()

    return jsonify({
        "success": True,
        "message": f"开始查询: {len(devices)} 台设备 × {len(commands)} 条命令",
        "devices_count": len(devices),
        "commands_count": len(commands),
    })


@app.route("/api/query/status")
def api_query_status():
    """获取CGI查询状态。"""
    return jsonify({
        "running": _query_running,
        "completed": _query_completed,
        "stopped": _query_stopped,
        "stop_requested": _query_stop_requested,
        "progress": _query_progress_data,
        "data": _query_result_data,
        "rows": _query_row_dicts,
        "columns": _query_result_columns,
        "count": len(_query_result_data),
        "devices": [_serialize_device_snapshot(device) for device in _device_loader.devices],
    })


@app.route("/api/query/stop", methods=["POST"])
def api_query_stop():
    """停止正在执行的CGI查询。"""
    global _query_stop_requested, _query_progress_data

    if not _query_running:
        return jsonify({
            "success": True,
            "message": "当前没有正在执行的查询任务",
            "running": False,
            "stopped": _query_stopped,
        })

    _query_stop_requested = True
    _query_progress_data["message"] = "正在停止..."
    _web_log_callback("收到查询停止请求", "WARNING")
    if _query_executor is not None:
        try:
            _query_executor.stop()
        except Exception as exc:
            _web_log_callback(f"停止查询执行器异常: {exc}", "ERROR")

    return jsonify({"success": True, "message": "已请求停止查询"})


@app.route("/api/query/export")
def api_query_export():
    """导出CGI查询结果为Excel文件"""
    global _query_executor, _query_result_data, _query_result_columns

    if not _query_result_data or not _query_result_columns:
        return jsonify({"error": "没有查询结果，请先执行查询"}), 400

    import tempfile
    import pandas as pd

    df = pd.DataFrame(_query_result_data, columns=_query_result_columns)
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp_path = tmp.name
    tmp.close()

    try:
        if _query_executor is None:
            _query_executor = CgiQueryExecutor(_config, _log_manager)
        _query_executor.export_to_excel(df, tmp_path)
        return send_file(
            tmp_path,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"CGI查询结果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        )
    except Exception as e:
        return jsonify({"error": f"导出失败: {str(e)}"}), 500


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
