#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# V10.1 - CGI 命令参考扩展: 包含设备实测的查询模板与返回字段

import json
import logging
import os
import re
import sys
from datetime import datetime
from typing import Dict, List, Optional


class CGIReferenceManager:
    """CGI 参数引用管理器 — 提供参数库、CGI 命令参考、模块分类等数据"""

    # ========== 模块定义 ==========

    DAHUA_MODULES = {
        "VideoWidget":      "视频叠加/OSD 配置",
        "ChannelTitle":     "通道标题",
        "VideoBoundary":    "视频边界",
        "RecordMode":       "录像模式",
        "Encode":           "编码参数",
        "System":           "系统设置",
        "Network":          "网络设置",
        "Storage":          "存储设置",
        "Alarm":            "告警管理",
        "SmartAnalysis":    "智能分析",
        "DeviceConfig":     "设备配置管理",
        "DeviceVerified":   "设备实测 CGI 范本",
    }

    # ========== CGI 命令参考（从 ConfigManager 加载） ==========

    _CGI_COMMANDS_LOADED = False
    CGI_COMMANDS: List[Dict] = []

    VERIFIED_GETCONFIG_TEMPLATES: List[Dict] = [
        {
            "name": "GetVerifiedGeneralConfig",
            "module": "DeviceVerified",
            "path": "/cgi-bin/configManager.cgi",
            "method": "GET",
            "auth": "digest",
            "timeout": 30,
            "description": "实测获取通用配置",
            "query_url": "http://{{IP}}:{{port}}/cgi-bin/configManager.cgi?action=getConfig&name=General",
            "set_url_template": "http://{{IP}}:{{port}}/cgi-bin/configManager.cgi?action=setConfig&{parameter}={value}",
            "verified": True,
            "response_fields": [
                "General.LocalNo",
                "General.LockLoginEnable",
                "General.LockLoginTimes",
                "General.LoginFailLockTime",
                "General.MachineName",
                "General.MaxOnlineTime",
            ],
            "params": [
                {"name": "action", "type": "string", "required": True, "default": "getConfig"},
                {"name": "name", "type": "string", "required": True, "default": "General"},
            ],
        },
        {
            "name": "GetVerifiedNetworkConfig",
            "module": "DeviceVerified",
            "path": "/cgi-bin/configManager.cgi",
            "method": "GET",
            "auth": "digest",
            "timeout": 30,
            "description": "实测获取 eth0 网络配置",
            "query_url": "http://{{IP}}:{{port}}/cgi-bin/configManager.cgi?action=getConfig&name=Network",
            "set_url_template": "http://{{IP}}:{{port}}/cgi-bin/configManager.cgi?action=setConfig&{parameter}={value}",
            "verified": True,
            "response_fields": [
                "Network.DefaultInterface",
                "Network.Domain",
                "Network.Hostname",
                "Network.eth0.DefaultGateway",
                "Network.eth0.DhcpEnable",
                "Network.eth0.DnsAutoGet",
                "Network.eth0.DnsServers[0]",
                "Network.eth0.DnsServers[1]",
                "Network.eth0.EnableDhcpReservedIP",
                "Network.eth0.IPAddress",
                "Network.eth0.MTU",
                "Network.eth0.PhysicalAddress",
                "Network.eth0.SubnetMask",
            ],
            "params": [
                {"name": "action", "type": "string", "required": True, "default": "getConfig"},
                {"name": "name", "type": "string", "required": True, "default": "Network"},
            ],
        },
        {
            "name": "GetVerifiedEncodeConfig",
            "module": "DeviceVerified",
            "path": "/cgi-bin/configManager.cgi",
            "method": "GET",
            "auth": "digest",
            "timeout": 30,
            "description": "实测获取主码流、辅码流和抓图编码配置",
            "query_url": "http://{{IP}}:{{port}}/cgi-bin/configManager.cgi?action=getConfig&name=Encode",
            "set_url_template": "http://{{IP}}:{{port}}/cgi-bin/configManager.cgi?action=setConfig&{parameter}={value}",
            "verified": True,
            "response_fields": [
                "Encode[0].MainFormat[{stream}].Video.{BitRate,BitRateControl,Compression,FPS,GOP,Height,Width,Profile,Quality,Priority}",
                "Encode[0].MainFormat[{stream}].Audio.{Bitrate,Channels[0],Compression,Depth,Frequency,Mode,Pack}",
                "Encode[0].ExtraFormat[{stream}].Video.{BitRate,BitRateControl,Compression,FPS,GOP,Height,Width,Profile,Quality,Priority}",
                "Encode[0].ExtraFormat[{stream}].Audio.{Bitrate,Channels[0],Compression,Depth,Frequency,Pack}",
                "Encode[0].SnapFormat[{stream}].Video.{BitRate,BitRateControl,Compression,FPS,GOP,Height,Width,Profile,Quality,Priority}",
                "Encode[0].{MainFormat,ExtraFormat,SnapFormat}[{stream}].{VideoEnable,AudioEnable}",
            ],
            "params": [
                {"name": "action", "type": "string", "required": True, "default": "getConfig"},
                {"name": "name", "type": "string", "required": True, "default": "Encode"},
            ],
        },
        {
            "name": "GetVerifiedVideoWidgetConfig",
            "module": "DeviceVerified",
            "path": "/cgi-bin/configManager.cgi",
            "method": "GET",
            "auth": "digest",
            "timeout": 30,
            "description": "实测获取 OSD、通道标题、自定义标题和视频边界配置",
            "query_url": "http://{{IP}}:{{port}}/cgi-bin/configManager.cgi?action=getConfig&name=VideoWidget",
            "set_url_template": "http://{{IP}}:{{port}}/cgi-bin/configManager.cgi?action=setConfig&{parameter}={value}",
            "verified": True,
            "response_fields": [
                "VideoWidget[0].ChannelTitle.{EncodeBlend,PreviewBlend,Rect[0..3],FrontColor[0..3],BackColor[0..3]}",
                "VideoWidget[0].CustomTitle[{index}].{EncodeBlend,PreviewBlend,Rect[0..3],Text,TextAlign,FrontColor[0..3],BackColor[0..3]}",
                "VideoWidget[0].UserDefinedTitle[0].{EncodeBlend,PreviewBlend,Rect[0..3],Text,TextAlign}",
                "VideoWidget[0].TimeTitle.{EncodeBlend,PreviewBlend,Rect[0..3],ShowWeek,WeekPosition}",
                "VideoWidget[0].VideoBoundary[0..3]",
                "VideoWidget[0].{FontColorType,FontSize,FontSizeScale,WideHeightRatio}",
            ],
            "params": [
                {"name": "action", "type": "string", "required": True, "default": "getConfig"},
                {"name": "name", "type": "string", "required": True, "default": "VideoWidget"},
            ],
        },
        {
            "name": "GetVerifiedRecordModeConfig",
            "module": "DeviceVerified",
            "path": "/cgi-bin/configManager.cgi",
            "method": "GET",
            "auth": "digest",
            "timeout": 30,
            "description": "实测获取录像模式配置",
            "query_url": "http://{{IP}}:{{port}}/cgi-bin/configManager.cgi?action=getConfig&name=RecordMode",
            "set_url_template": "http://{{IP}}:{{port}}/cgi-bin/configManager.cgi?action=setConfig&{parameter}={value}",
            "verified": True,
            "response_fields": [
                "RecordMode[0].Mode",
                "RecordMode[0].ModeExtra1",
            ],
            "params": [
                {"name": "action", "type": "string", "required": True, "default": "getConfig"},
                {"name": "name", "type": "string", "required": True, "default": "RecordMode"},
            ],
        },
        {
            "name": "GetVerifiedVideoInModeConfig",
            "module": "DeviceVerified",
            "path": "/cgi-bin/configManager.cgi",
            "method": "GET",
            "auth": "digest",
            "timeout": 30,
            "description": "实测获取视频输入模式和按周时段配置",
            "query_url": "http://{{IP}}:{{port}}/cgi-bin/configManager.cgi?action=getConfig&name=VideoInMode",
            "set_url_template": "http://{{IP}}:{{port}}/cgi-bin/configManager.cgi?action=setConfig&{parameter}={value}",
            "verified": True,
            "response_fields": [
                "VideoInMode[0].Config[0]",
                "VideoInMode[0].Mode",
                "VideoInMode[0].TimeSection[{day}][{period}]",
            ],
            "params": [
                {"name": "action", "type": "string", "required": True, "default": "getConfig"},
                {"name": "name", "type": "string", "required": True, "default": "VideoInMode"},
            ],
        },
        {
            "name": "GetVerifiedMotionDetectConfig",
            "module": "DeviceVerified",
            "path": "/cgi-bin/configManager.cgi",
            "method": "GET",
            "auth": "digest",
            "timeout": 30,
            "description": "实测获取移动侦测、联动、计划和区域配置",
            "query_url": "http://{{IP}}:{{port}}/cgi-bin/configManager.cgi?action=getConfig&name=MotionDetect",
            "set_url_template": "http://{{IP}}:{{port}}/cgi-bin/configManager.cgi?action=setConfig&{parameter}={value}",
            "verified": True,
            "response_fields": [
                "MotionDetect[0].{Enable,Level,OsdTwinkleEnable,PirMotionLevel,PtzManualEnable}",
                "MotionDetect[0].MotionDetectWindow[{index}].{Id,Name,Region[0..17],Sensitive,Threshold,Window[0..3]}",
                "MotionDetect[0].EventHandler.{AlarmOutEnable,BeepEnable,Delay,Dejitter,MailEnable,MessageEnable,RecordEnable,RecordLatch,SnapshotEnable,SnapshotTimes}",
                "MotionDetect[0].EventHandler.{TimeSection,LightingLink.WhiteLightTimeSection}[{day}][{period}]",
                "MotionDetect[0].EventHandler.PtzLink[0][{index}]",
            ],
            "params": [
                {"name": "action", "type": "string", "required": True, "default": "getConfig"},
                {"name": "name", "type": "string", "required": True, "default": "MotionDetect"},
            ],
        },
    ]

    VERIFIED_SETCONFIG_OPTIONS: List[Dict] = [
        {
            "module": "DeviceConfig",
            "parameter": "General.MachineName",
            "type": "string",
            "description": "设备名称",
            "example": "Camera-01",
        },
        {
            "module": "Network",
            "parameter": "Network.eth0.DhcpEnable",
            "type": "bool",
            "description": "eth0 DHCP 开关",
            "example": "true",
        },
        {
            "module": "Network",
            "parameter": "Network.eth0.IPAddress",
            "type": "string",
            "description": "eth0 IPv4 地址",
            "example": "10.17.1.62",
        },
        {
            "module": "Network",
            "parameter": "Network.eth0.SubnetMask",
            "type": "string",
            "description": "eth0 子网掩码",
            "example": "255.255.255.0",
        },
        {
            "module": "Network",
            "parameter": "Network.eth0.DefaultGateway",
            "type": "string",
            "description": "eth0 默认网关",
            "example": "10.17.1.1",
        },
        {
            "module": "Network",
            "parameter": "Network.eth0.DnsServers[0]",
            "type": "string",
            "description": "首选 DNS",
            "example": "223.5.5.5",
        },
        {
            "module": "Encode",
            "parameter": "Encode[0].MainFormat[0].Video.Compression",
            "type": "string",
            "description": "主码流编码格式",
            "example": "H.265",
        },
        {
            "module": "Encode",
            "parameter": "Encode[0].MainFormat[0].Video.BitRate",
            "type": "int",
            "description": "主码流码率",
            "example": "2048",
        },
        {
            "module": "Encode",
            "parameter": "Encode[0].MainFormat[0].Video.FPS",
            "type": "int",
            "description": "主码流帧率",
            "example": "25",
        },
        {
            "module": "Encode",
            "parameter": "Encode[0].MainFormat[0].Video.GOP",
            "type": "int",
            "description": "主码流 GOP",
            "example": "50",
        },
        {
            "module": "VideoWidget",
            "parameter": "VideoWidget[0].ChannelTitle.EncodeBlend",
            "type": "bool",
            "description": "通道标题编码叠加",
            "example": "true",
        },
        {
            "module": "VideoWidget",
            "parameter": "VideoWidget[0].ChannelTitle.PreviewBlend",
            "type": "bool",
            "description": "通道标题预览叠加",
            "example": "true",
        },
        {
            "module": "VideoWidget",
            "parameter": "VideoWidget[0].ChannelTitle.Rect[0]",
            "type": "int",
            "description": "通道标题矩形左边界",
            "example": "5259",
        },
        {
            "module": "VideoWidget",
            "parameter": "VideoWidget[0].CustomTitle[0].Text",
            "type": "string",
            "description": "自定义标题文字",
            "example": "Camera-01",
        },
        {
            "module": "VideoWidget",
            "parameter": "VideoWidget[0].CustomTitle[0].EncodeBlend",
            "type": "bool",
            "description": "自定义标题编码叠加",
            "example": "true",
        },
        {
            "module": "RecordMode",
            "parameter": "RecordMode[0].Mode",
            "type": "int",
            "description": "录像模式",
            "example": "0",
        },
        {
            "module": "VideoInMode",
            "parameter": "VideoInMode[0].Mode",
            "type": "int",
            "description": "视频输入模式",
            "example": "0",
        },
        {
            "module": "MotionDetect",
            "parameter": "MotionDetect[0].Enable",
            "type": "bool",
            "description": "移动侦测开关",
            "example": "true",
        },
        {
            "module": "MotionDetect",
            "parameter": "MotionDetect[0].Level",
            "type": "int",
            "description": "移动侦测等级",
            "example": "3",
        },
    ]

    @classmethod
    def _ensure_commands_loaded(cls) -> None:
        """确保 CGI 命令从配置加载（延迟加载，避免循环导入）"""
        if cls._CGI_COMMANDS_LOADED:
            return
        cls._CGI_COMMANDS_LOADED = True
        try:
            # 延迟导入避免循环依赖
            from utils.config_manager import ConfigManager
            config = ConfigManager.load_config()
            raw_commands = config.get("cgi_commands", [])
            cls.CGI_COMMANDS = cls._normalize_commands(raw_commands)
        except Exception as e:
            logging.warning(f"从 ConfigManager 加载 CGI 命令失败: {e}，使用空列表")
            cls.CGI_COMMANDS = []

    @staticmethod
    def _normalize_commands(raw_commands: List[Dict]) -> List[Dict]:
        """将结构化命令和旧版 key=value 命令转换为标准参考格式。"""
        result = []
        for cmd in raw_commands:
            if isinstance(cmd, str):
                parameter, separator, value = cmd.partition("=")
                result.append({
                    "name": f"SetConfig:{parameter}" if parameter else "SetConfig",
                    "module": "DeviceConfig",
                    "path": "/cgi-bin/configManager.cgi",
                    "method": "GET",
                    "auth": "digest",
                    "timeout": 30,
                    "description": "用户配置的 setConfig 命令",
                    "raw_command": cmd,
                    "params": [
                        {
                            "name": "action",
                            "type": "string",
                            "required": True,
                            "default": "setConfig",
                        },
                        {
                            "name": parameter,
                            "type": "string",
                            "required": bool(separator),
                            "default": value,
                        },
                    ],
                })
                continue

            if not isinstance(cmd, dict):
                logging.warning("忽略不支持的 CGI 命令格式: %r", cmd)
                continue

            normalized = dict(cmd)
            # 确保所有字段存在
            normalized.setdefault("method", "GET")
            normalized.setdefault("auth", "digest")
            normalized.setdefault("timeout", 30)
            normalized.setdefault("description", "")
            normalized.setdefault("params", [])
            result.append(normalized)
        return result

    @classmethod
    def get_verified_getconfig_templates(cls) -> List[Dict]:
        """返回已在授权设备上验证成功的只读 getConfig 查询范本。"""
        return [dict(template) for template in cls.VERIFIED_GETCONFIG_TEMPLATES]

    @classmethod
    def get_verified_setconfig_options(cls) -> List[Dict]:
        """返回可选择的实测 setConfig 参数和值示例。"""
        return [dict(option) for option in cls.VERIFIED_SETCONFIG_OPTIONS]

    @staticmethod
    def get_query_library() -> List[Dict]:
        """按参数库模块生成可选择的 getConfig 查询库。"""
        reference = CGIReferenceManager.load_reference()
        params = reference.get("参数库", [])
        templates = CGIReferenceManager.get_verified_getconfig_templates()
        by_module: Dict[str, Dict] = {}

        for template in templates:
            module = template["params"][1]["default"]
            by_module[module] = {
                "name": template.get("name", f"Get{module}Config"),
                "module": module,
                "description": template.get("description", f"获取 {module} 配置"),
                "query_url": template["query_url"],
                "verified": template.get("verified", False),
                "params": [],
                "response_fields": template.get("response_fields", []),
            }

        for param in params:
            module = CGIReferenceManager._get_config_name_from_param(param.get("param", ""))
            if not module:
                module = CGIReferenceManager._module_to_config_name(param.get("module", "Unknown"))
            if module not in by_module:
                by_module[module] = {
                    "name": f"Get{module}Config",
                    "module": module,
                    "description": f"获取 {module} 配置",
                    "query_url": (
                        "http://{{IP}}:{{port}}/cgi-bin/configManager.cgi"
                        f"?action=getConfig&name={module}"
                    ),
                    "verified": False,
                    "params": [],
                    "response_fields": [],
                }
            by_module[module]["params"].append(dict(param))

        for endpoint in reference.get("只读CGI端点", []):
            module = endpoint.get("name", "ReadOnly")
            by_module[module] = {
                "name": endpoint.get("name", module),
                "module": module,
                "description": endpoint.get("description", module),
                "query_url": endpoint.get("query_url", ""),
                "verified": endpoint.get("verified", False),
                "params": [],
                "response_fields": [
                    f"{field.get('name', '')} ({field.get('type', 'string')})"
                    for field in endpoint.get("fields", [])
                ],
                "endpoint_type": "readonly",
            }

        def sort_key(item: Dict) -> tuple:
            verified_rank = 0 if item.get("verified") else 1
            endpoint_rank = 1 if item.get("endpoint_type") == "readonly" else 0
            return verified_rank, endpoint_rank, item.get("module", "")

        return sorted(by_module.values(), key=sort_key)

    @staticmethod
    def get_setconfig_library() -> List[Dict]:
        """从参数库生成可配置参数选项。"""
        reference = CGIReferenceManager.load_reference()
        options = []
        seen = set()
        for param in reference.get("参数库", []):
            parameter = param.get("param", "")
            if not parameter or parameter in seen:
                continue
            seen.add(parameter)
            options.append({
                "module": CGIReferenceManager._get_config_name_from_param(parameter)
                    or CGIReferenceManager._module_to_config_name(param.get("module", "Unknown")),
                "parameter": parameter,
                "type": param.get("type", "string"),
                "description": param.get("desc", ""),
                "example": param.get("example", param.get("default", "")),
                "default": param.get("default", ""),
            })
        return options

    @staticmethod
    def _get_config_name_from_param(parameter: str) -> str:
        """从 table 风格参数名推导 getConfig 的 name。"""
        root = parameter.split(".", 1)[0].strip()
        if not root:
            return ""
        root = re.sub(r"\[.*\]$", "", root)
        if root.lower() == "general":
            return "General"
        return root

    @staticmethod
    def _module_to_config_name(module: str) -> str:
        if module == "DeviceConfig":
            return "General"
        if module == "System":
            return "General"
        if module == "ChannelTitle" or module == "VideoBoundary":
            return "VideoWidget"
        return module

    @staticmethod
    def get_command_list():
        """返回 CGI 命令参考列表"""
        CGIReferenceManager._ensure_commands_loaded()
        return list(CGIReferenceManager.CGI_COMMANDS)

    @staticmethod
    def get_default_reference_data():
        """返回非空默认参数库（含告警/智能分析/设备管理扩展参数）"""
        base = [
            # ---- VideoWidget ----
            {
                "param": "VideoWidget[0].CustomTitle[0].EncodeBlend",
                "module": "VideoWidget",
                "type": "bool",
                "default": "false",
                "desc": "自定义标题编码叠加",
                "example": "true",
            },
            {
                "param": "VideoWidget[0].CustomTitle[0].PreviewBlend",
                "module": "VideoWidget",
                "type": "bool",
                "default": "false",
                "desc": "自定义标题预览叠加",
                "example": "true",
            },
            {
                "param": "VideoWidget[0].CustomTitle[0].Text",
                "module": "VideoWidget",
                "type": "string",
                "default": "",
                "desc": "自定义标题文字内容",
                "example": "日照职业技术学院天台山校区",
            },
            {
                "param": "VideoWidget[0].CustomTitle[0].TextAlign",
                "module": "VideoWidget",
                "type": "int",
                "default": "0",
                "desc": "文字对齐: 0=左, 1=居中, 2=右",
                "example": "2",
            },
            {
                "param": "VideoWidget[0].CustomTitle[0].Rect",
                "module": "VideoWidget",
                "type": "rect",
                "default": "0,0,0,0",
                "desc": "自定义标题矩形区域 (x1,y1,x2,y2)",
                "example": "5207,6631,7828,7069",
            },
            # ---- ChannelTitle ----
            {
                "param": "VideoWidget[0].ChannelTitle.EncodeBlend",
                "module": "ChannelTitle",
                "type": "bool",
                "default": "false",
                "desc": "通道标题编码叠加",
                "example": "true",
            },
            {
                "param": "VideoWidget[0].ChannelTitle.PreviewBlend",
                "module": "ChannelTitle",
                "type": "bool",
                "default": "false",
                "desc": "通道标题预览叠加",
                "example": "true",
            },
            {
                "param": "VideoWidget[0].ChannelTitle.Rect",
                "module": "ChannelTitle",
                "type": "rect",
                "default": "0,0,0,0",
                "desc": "通道标题矩形区域",
                "example": "5259,7155,7880,7595",
            },
            # ---- VideoBoundary ----
            {
                "param": "VideoWidget[0].VideoBoundary",
                "module": "VideoBoundary",
                "type": "int",
                "default": "0",
                "desc": "视频边界启用",
                "example": "1",
            },
            # ---- RecordMode ----
            {
                "param": "RecordMode[0].TimeSection[0][0].Type",
                "module": "RecordMode",
                "type": "string",
                "default": "",
                "desc": "录像时段类型",
                "example": "0",
            },
            # ---- Encode ----
            {
                "param": "Encode[0].MainFormat[0].Video.Compression",
                "module": "Encode",
                "type": "string",
                "default": "H.264",
                "desc": "主码流编码格式",
                "example": "H.265",
            },
            {
                "param": "Encode[0].MainFormat[0].Video.Resolution",
                "module": "Encode",
                "type": "string",
                "default": "1920x1080",
                "desc": "主码流分辨率",
                "example": "2560x1440",
            },
            # ---- System ----
            {
                "param": "general.systemTime",
                "module": "System",
                "type": "string",
                "default": "",
                "desc": "系统时间 (GET only)",
                "example": "getCurrentTime",
            },
            # ---- Storage ----
            {
                "param": "Storage.Stat.UsedBytes",
                "module": "Storage",
                "type": "int",
                "default": "0",
                "desc": "已用存储字节数 (GET only)",
                "example": "1073741824",
            },
            {
                "param": "Storage.Stat.TotalBytes",
                "module": "Storage",
                "type": "int",
                "default": "0",
                "desc": "总存储字节数 (GET only)",
                "example": "4294967296",
            },
        ]

        # ---- 告警相关参数 (Alarm) ----
        alarm_params = [
            {
                "param": "AlarmOut[0].Mode",
                "module": "Alarm",
                "type": "int",
                "default": "0",
                "desc": "告警输出模式: 0=关闭, 1=常开, 2=脉冲",
                "example": "1",
            },
            {
                "param": "AlarmOut[0].Channel",
                "module": "Alarm",
                "type": "int",
                "default": "0",
                "desc": "告警输出通道",
                "example": "1",
            },
            {
                "param": "MotionDetect[0].Enable",
                "module": "Alarm",
                "type": "bool",
                "default": "false",
                "desc": "移动侦测启用",
                "example": "true",
            },
            {
                "param": "MotionDetect[0].Sensitivity",
                "module": "Alarm",
                "type": "int",
                "default": "3",
                "desc": "移动侦测灵敏度 (1-6)",
                "example": "5",
            },
            {
                "param": "VideoBlind[0].Enable",
                "module": "Alarm",
                "type": "bool",
                "default": "false",
                "desc": "视频遮挡检测启用",
                "example": "true",
            },
            {
                "param": "VideoLoss[0].Enable",
                "module": "Alarm",
                "type": "bool",
                "default": "false",
                "desc": "视频丢失检测启用",
                "example": "true",
            },
            {
                "param": "VideoBlind[0].Sensitivity",
                "module": "Alarm",
                "type": "int",
                "default": "3",
                "desc": "视频遮挡灵敏度",
                "example": "5",
            },
            {
                "param": "AlarmOut[0].State",
                "module": "Alarm",
                "type": "int",
                "default": "0",
                "desc": "告警输出状态: 0=关闭, 1=开启",
                "example": "1",
            },
        ]

        # ---- 智能分析参数 (SmartAnalysis) ----
        smart_params = [
            {
                "param": "SmartAnalysis[0].Enable",
                "module": "SmartAnalysis",
                "type": "bool",
                "default": "false",
                "desc": "智能分析启用",
                "example": "true",
            },
            {
                "param": "SmartAnalysis[0].EventType",
                "module": "SmartAnalysis",
                "type": "string",
                "default": "",
                "desc": "智能分析事件类型",
                "example": "IntrusionDetection",
            },
            {
                "param": "VideoAnalyze[0].Enable",
                "module": "SmartAnalysis",
                "type": "bool",
                "default": "false",
                "desc": "视频分析启用",
                "example": "true",
            },
            {
                "param": "VideoAnalyze[0].DetectType",
                "module": "SmartAnalysis",
                "type": "string",
                "default": "",
                "desc": "检测类型（Intrusion/Loitering/Park等）",
                "example": "Intrusion",
            },
            {
                "param": "VideoAnalyze[0].Rule[0].Enable",
                "module": "SmartAnalysis",
                "type": "bool",
                "default": "false",
                "desc": "视频分析规则启用",
                "example": "true",
            },
        ]

        # ---- 设备管理参数 (DeviceConfig) ----
        device_params = [
            {
                "param": "General.MachineName",
                "module": "DeviceConfig",
                "type": "string",
                "default": "",
                "desc": "设备名称",
                "example": "Camera-01",
            },
            {
                "param": "General.Language",
                "module": "DeviceConfig",
                "type": "string",
                "default": "zh",
                "desc": "系统语言",
                "example": "en",
            },
            {
                "param": "General.VideoFormat",
                "module": "DeviceConfig",
                "type": "string",
                "default": "PAL",
                "desc": "视频制式",
                "example": "NTSC",
            },
            {
                "param": "General.SerialNo",
                "module": "DeviceConfig",
                "type": "string",
                "default": "",
                "desc": "设备序列号 (GET only)",
                "example": "ND6234567890123",
            },
            {
                "param": "Network.IPAddress",
                "module": "Network",
                "type": "string",
                "default": "192.168.1.108",
                "desc": "设备IP地址",
                "example": "10.0.0.100",
            },
            {
                "param": "Network.SubnetMask",
                "module": "Network",
                "type": "string",
                "default": "255.255.255.0",
                "desc": "子网掩码",
                "example": "255.255.0.0",
            },
            {
                "param": "Network.Gateway",
                "module": "Network",
                "type": "string",
                "default": "192.168.1.1",
                "desc": "默认网关",
                "example": "10.0.0.1",
            },
            {
                "param": "Network.DNS",
                "module": "Network",
                "type": "string",
                "default": "8.8.8.8",
                "desc": "DNS服务器",
                "example": "114.114.114.114",
            },
            {
                "param": "Network.DHCP",
                "module": "Network",
                "type": "bool",
                "default": "true",
                "desc": "DHCP启用",
                "example": "false",
            },
            {
                "param": "General.Time.TimeZone",
                "module": "System",
                "type": "string",
                "default": "CST-8",
                "desc": "时区",
                "example": "UTC+8:00",
            },
            {
                "param": "General.Time.SyncType",
                "module": "System",
                "type": "string",
                "default": "Manual",
                "desc": "时间同步类型 (Manual/NTP)",
                "example": "NTP",
            },
            {
                "param": "General.Time.NTPServer",
                "module": "System",
                "type": "string",
                "default": "ntp.aliyun.com",
                "desc": "NTP服务器地址",
                "example": "pool.ntp.org",
            },
        ]

        return base + alarm_params + smart_params + device_params

    # ========== 路径工具 ==========

    @staticmethod
    def get_app_directory():
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        else:
            return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    @staticmethod
    def get_config_directory():
        app_dir = CGIReferenceManager.get_app_directory()
        config_dir = os.path.join(app_dir, "config")
        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
        return config_dir

    @staticmethod
    def get_reference_path():
        return os.path.join(CGIReferenceManager.get_config_directory(), "cgi_reference.json")

    @staticmethod
    def get_module_categories():
        return list(CGIReferenceManager.DAHUA_MODULES.keys())

    # ========== 查询方法 ==========

    @staticmethod
    def get_commands_by_module(module: str) -> List[Dict]:
        """查询指定模块的所有 CGI 命令"""
        CGIReferenceManager._ensure_commands_loaded()
        return [cmd for cmd in CGIReferenceManager.CGI_COMMANDS if cmd.get("module") == module]

    @staticmethod
    def get_command(command_name: str) -> Optional[Dict]:
        """按命令名查询单条 CGI 命令"""
        CGIReferenceManager._ensure_commands_loaded()
        for cmd in CGIReferenceManager.CGI_COMMANDS:
            if cmd.get("name") == command_name:
                return cmd
        return None

    @staticmethod
    def get_params_by_module(module: str) -> List[Dict]:
        """查询指定模块的所有参数"""
        return [p for p in CGIReferenceManager.get_default_reference_data() if p["module"] == module]

    @staticmethod
    def search_commands(keyword: str) -> List[Dict]:
        """搜索命令（按命令名或描述模糊匹配）"""
        CGIReferenceManager._ensure_commands_loaded()
        kw = keyword.lower()
        return [
            cmd for cmd in CGIReferenceManager.CGI_COMMANDS
            if kw in cmd.get("name", "").lower() or kw in cmd.get("description", "").lower()
        ]

    @staticmethod
    def search_params(keyword: str) -> List[Dict]:
        """搜索参数（按参数名或描述模糊匹配）"""
        kw = keyword.lower()
        return [
            p for p in CGIReferenceManager.get_default_reference_data()
            if kw in p["param"].lower() or kw in p["desc"].lower()
        ]

    # ========== 加载 / 保存 ==========

    @staticmethod
    def load_reference():
        CGIReferenceManager._ensure_commands_loaded()
        reference_file = CGIReferenceManager.get_reference_path()
        default_reference_data = CGIReferenceManager.get_default_reference_data()
        default_reference = {
            "version": "10.1",
            "last_updated": datetime.now().strftime("%Y-%m-%d"),
            "total_parameters": len(default_reference_data),
            "total_commands": len(CGIReferenceManager.CGI_COMMANDS),
            "参数库": default_reference_data,
            "CGI命令参考": CGIReferenceManager.CGI_COMMANDS,
            "设备实测查询范本": CGIReferenceManager.get_verified_getconfig_templates(),
            "模块分类": CGIReferenceManager.get_module_categories(),
        }
        try:
            if not os.path.exists(reference_file):
                CGIReferenceManager.save_reference(default_reference)
                return default_reference
            with open(reference_file, "r", encoding="utf-8") as f:
                reference = json.load(f)
            reference["version"] = "10.1"
            reference["last_updated"] = datetime.now().strftime("%Y-%m-%d")

            # 确保参数库非空
            params = reference.get("参数库", [])
            if not params:
                params = list(default_reference_data)
                reference["参数库"] = params
            reference["total_parameters"] = len(params)

            # 确保 CGI 命令参考存在
            if "CGI命令参考" not in reference or not reference["CGI命令参考"]:
                reference["CGI命令参考"] = CGIReferenceManager.CGI_COMMANDS
            reference["total_commands"] = len(reference.get("CGI命令参考", []))

            if "设备实测查询范本" not in reference or not reference["设备实测查询范本"]:
                reference["设备实测查询范本"] = CGIReferenceManager.get_verified_getconfig_templates()

            # 确保模块分类完整
            categories = reference.get("模块分类", [])
            if not categories:
                categories = CGIReferenceManager.get_module_categories()
                reference["模块分类"] = categories

            return reference
        except Exception as e:
            logging.warning(f"加载 cgi_reference.json 失败: {e}，使用默认值")
            return default_reference

    @staticmethod
    def save_reference(reference):
        CGIReferenceManager._ensure_commands_loaded()
        try:
            reference_file = CGIReferenceManager.get_reference_path()
            if "参数库" not in reference or not reference["参数库"]:
                reference["参数库"] = CGIReferenceManager.get_default_reference_data()
            reference["version"] = "10.1"
            reference["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            reference["total_parameters"] = len(reference.get("参数库", []))

            if "CGI命令参考" not in reference or not reference["CGI命令参考"]:
                reference["CGI命令参考"] = CGIReferenceManager.CGI_COMMANDS
            reference["total_commands"] = len(reference.get("CGI命令参考", []))

            if "设备实测查询范本" not in reference or not reference["设备实测查询范本"]:
                reference["设备实测查询范本"] = CGIReferenceManager.get_verified_getconfig_templates()

            if "模块分类" not in reference or not reference["模块分类"]:
                reference["模块分类"] = CGIReferenceManager.get_module_categories()
            config_dir = os.path.dirname(reference_file)
            if not os.path.exists(config_dir):
                os.makedirs(config_dir, exist_ok=True)
            with open(reference_file, "w", encoding="utf-8") as f:
                json.dump(reference, f, ensure_ascii=False, indent=4, sort_keys=True)
            return True
        except Exception as e:
            logging.error(f"保存 cgi_reference.json 失败: {e}")
            return False
