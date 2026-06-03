#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# V10.0 - CGI 命令扩展: 告警/智能分析/设备管理命令 + 参数库扩展

import json
import logging
import os
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
    }

    # ========== CGI 命令参考 ==========

    CGI_COMMANDS = [
        # ---- 告警相关 (Alarm) ----
        {
            "command": "GetAlarmRecord",
            "module": "Alarm",
            "action": "getAlarmRecord",
            "method": "GET",
            "description": "获取告警记录",
            "url_example": "/cgi-bin/eventManager.cgi?action=getAlarmRecord&pageNo=1&pageSize=10",
            "params": [
                {"name": "pageNo",      "type": "int",    "required": True,  "default": "1",   "desc": "页码"},
                {"name": "pageSize",    "type": "int",    "required": True,  "default": "20",  "desc": "每页条数"},
                {"name": "startTime",   "type": "string", "required": False, "default": "",    "desc": "开始时间 (yyyy-MM-dd HH:mm:ss)"},
                {"name": "endTime",     "type": "string", "required": False, "default": "",    "desc": "结束时间 (yyyy-MM-dd HH:mm:ss)"},
                {"name": "eventType",   "type": "string", "required": False, "default": "",    "desc": "事件类型过滤"},
                {"name": "channel",     "type": "int",    "required": False, "default": "0",   "desc": "通道号"},
            ],
            "returns": {
                "format": "XML",
                "fields": [
                    {"name": "alarmRecord",       "desc": "告警记录列表"},
                    {"name": "alarmRecord.ID",    "desc": "记录ID"},
                    {"name": "alarmRecord.Time",  "desc": "告警时间"},
                    {"name": "alarmRecord.Type",  "desc": "告警类型（如 MotionDetection, VideoLoss）"},
                    {"name": "alarmRecord.Channel","desc": "告警通道"},
                    {"name": "alarmRecord.Status","desc": "告警状态（Start/Stop）"},
                    {"name": "found",             "desc": "匹配记录总数"},
                ],
            },
        },
        {
            "command": "GetAlarmConfig",
            "module": "Alarm",
            "action": "getConfig",
            "method": "GET",
            "description": "获取告警配置",
            "url_example": "/cgi-bin/configManager.cgi?action=getConfig&name=AlarmOut",
            "params": [
                {"name": "name",  "type": "string", "required": True,  "default": "AlarmOut",     "desc": "配置名称（如 AlarmOut, MotionDetect, VideoLoss, VideoBlind）"},
            ],
            "returns": {
                "format": "table",
                "fields": [
                    {"name": "table.AlarmOut",        "desc": "告警输出配置表"},
                    {"name": "table.AlarmOut.Channel","desc": "告警输出通道"},
                    {"name": "table.AlarmOut.Mode",   "desc": "告警输出模式（0=关闭, 1=常开, 2=脉冲）"},
                ],
            },
        },
        {
            "command": "SetAlarmConfig",
            "module": "Alarm",
            "action": "setConfig",
            "method": "GET",
            "description": "设置告警配置",
            "url_example": "/cgi-bin/configManager.cgi?action=setConfig&AlarmOut[0].Mode=1",
            "params": [
                {"name": "AlarmOut[0].Mode",           "type": "int",    "required": False, "default": "", "desc": "告警输出模式: 0=关闭, 1=常开, 2=脉冲"},
                {"name": "AlarmOut[0].Channel",         "type": "int",    "required": False, "default": "", "desc": "告警输出通道"},
                {"name": "AlarmOut[0].State",           "type": "string", "required": False, "default": "", "desc": "告警输出状态"},
                {"name": "VideoBlind[0].Enable",        "type": "bool",   "required": False, "default": "", "desc": "视频遮挡检测启用"},
                {"name": "VideoLoss[0].Enable",         "type": "bool",   "required": False, "default": "", "desc": "视频丢失检测启用"},
                {"name": "MotionDetect[0].Enable",      "type": "bool",   "required": False, "default": "", "desc": "移动侦测启用"},
            ],
            "returns": {
                "format": "text",
                "fields": [
                    {"name": "OK", "desc": "设置成功"},
                    {"name": "Error", "desc": "设置失败及错误信息"},
                ],
            },
        },
        {
            "command": "GetEventType",
            "module": "Alarm",
            "action": "getEventType",
            "method": "GET",
            "description": "获取设备支持的事件类型列表",
            "url_example": "/cgi-bin/eventManager.cgi?action=getEventType",
            "params": [],
            "returns": {
                "format": "XML",
                "fields": [
                    {"name": "eventType",            "desc": "事件类型"},
                    {"name": "eventType.ID",         "desc": "事件类型ID"},
                    {"name": "eventType.Name",       "desc": "事件类型名称"},
                    {"name": "eventType.Description","desc": "事件描述"},
                ],
            },
        },
        # ---- 智能分析 (SmartAnalysis) ----
        {
            "command": "GetSmartAnalysis",
            "module": "SmartAnalysis",
            "action": "getConfig",
            "method": "GET",
            "description": "获取智能分析配置",
            "url_example": "/cgi-bin/configManager.cgi?action=getConfig&name=SmartAnalysis",
            "params": [
                {"name": "name", "type": "string", "required": True, "default": "SmartAnalysis", "desc": "配置名称（如 SmartAnalysis, IntelligentBusiness）"},
            ],
            "returns": {
                "format": "table",
                "fields": [
                    {"name": "table.SmartAnalysis",          "desc": "智能分析配置表"},
                    {"name": "table.SmartAnalysis.Enable",   "desc": "智能分析启用/关闭"},
                    {"name": "table.SmartAnalysis.Support",  "desc": "支持的智能分析类型"},
                ],
            },
        },
        {
            "command": "GetFaceInfo",
            "module": "SmartAnalysis",
            "action": "getFaceInfo",
            "method": "GET",
            "description": "获取人脸检测信息",
            "url_example": "/cgi-bin/faceManager.cgi?action=getFaceInfo",
            "params": [
                {"name": "channel",   "type": "int",    "required": False, "default": "0",   "desc": "通道号"},
                {"name": "pageNo",    "type": "int",    "required": False, "default": "1",   "desc": "页码"},
                {"name": "pageSize",  "type": "int",    "required": False, "default": "20",  "desc": "每页条数"},
            ],
            "returns": {
                "format": "XML",
                "fields": [
                    {"name": "faceInfo",              "desc": "人脸信息列表"},
                    {"name": "faceInfo.Gender",       "desc": "性别"},
                    {"name": "faceInfo.Age",          "desc": "年龄"},
                    {"name": "faceInfo.FaceRect",     "desc": "人脸矩形区域"},
                    {"name": "faceInfo.SnapImage",    "desc": "抓拍图片"},
                    {"name": "faceInfo.HaveMask",     "desc": "是否戴口罩"},
                ],
            },
        },
        {
            "command": "GetVideoAnalyze",
            "module": "SmartAnalysis",
            "action": "getConfig",
            "method": "GET",
            "description": "获取视频分析配置",
            "url_example": "/cgi-bin/configManager.cgi?action=getConfig&name=VideoAnalyze",
            "params": [
                {"name": "name", "type": "string", "required": True, "default": "VideoAnalyze", "desc": "配置名称"},
            ],
            "returns": {
                "format": "table",
                "fields": [
                    {"name": "table.VideoAnalyze",              "desc": "视频分析配置"},
                    {"name": "table.VideoAnalyze.DetectType",   "desc": "检测类型（如 Intrusion, Loitering, Park 等）"},
                    {"name": "table.VideoAnalyze.Rule",         "desc": "规则配置"},
                    {"name": "table.VideoAnalyze.Enable",       "desc": "是否启用"},
                ],
            },
        },
        # ---- 设备管理 (DeviceConfig) ----
        {
            "command": "GetDeviceConfig",
            "module": "DeviceConfig",
            "action": "getConfig",
            "method": "GET",
            "description": "获取设备通用配置",
            "url_example": "/cgi-bin/configManager.cgi?action=getConfig&name=General",
            "params": [
                {"name": "name", "type": "string", "required": True, "default": "General", "desc": "配置名称（如 General, Serial, USB, PTZ）"},
            ],
            "returns": {
                "format": "table",
                "fields": [
                    {"name": "table.General",              "desc": "通用配置表"},
                    {"name": "table.General.SerialNo",     "desc": "设备序列号"},
                    {"name": "table.General.MachineName",  "desc": "设备名称"},
                    {"name": "table.General.Language",     "desc": "系统语言"},
                    {"name": "table.General.VideoFormat",  "desc": "视频制式"},
                ],
            },
        },
        {
            "command": "SetDeviceConfig",
            "module": "DeviceConfig",
            "action": "setConfig",
            "method": "GET",
            "description": "设置设备通用配置",
            "url_example": "/cgi-bin/configManager.cgi?action=setConfig&General.MachineName=MyCamera",
            "params": [
                {"name": "General.MachineName",    "type": "string", "required": False, "default": "", "desc": "设备名称"},
                {"name": "General.Language",       "type": "string", "required": False, "default": "", "desc": "系统语言（如 zh, en）"},
                {"name": "General.VideoFormat",    "type": "string", "required": False, "default": "", "desc": "视频制式（NTSC/PAL）"},
                {"name": "General.AutoMaintain",   "type": "string", "required": False, "default": "", "desc": "自动维护时间"},
            ],
            "returns": {
                "format": "text",
                "fields": [
                    {"name": "OK",    "desc": "设置成功"},
                    {"name": "Error", "desc": "设置失败及原因"},
                ],
            },
        },
        {
            "command": "GetNetworkConfig",
            "module": "Network",
            "action": "getConfig",
            "method": "GET",
            "description": "获取网络配置",
            "url_example": "/cgi-bin/configManager.cgi?action=getConfig&name=Network",
            "params": [
                {"name": "name", "type": "string", "required": True, "default": "Network", "desc": "配置名称（如 Network, PPPoE, DDNS, SMTP, FTP, NTP）"},
            ],
            "returns": {
                "format": "table",
                "fields": [
                    {"name": "table.Network",          "desc": "网络配置表"},
                    {"name": "table.Network.IPAddress","desc": "IP地址"},
                    {"name": "table.Network.SubnetMask","desc": "子网掩码"},
                    {"name": "table.Network.Gateway",  "desc": "默认网关"},
                    {"name": "table.Network.DNS",      "desc": "DNS服务器"},
                    {"name": "table.Network.MacAddress","desc": "MAC地址"},
                    {"name": "table.Network.DHCP",     "desc": "DHCP启用"},
                ],
            },
        },
        {
            "command": "GetTimeConfig",
            "module": "System",
            "action": "getConfig",
            "method": "GET",
            "description": "获取时间配置",
            "url_example": "/cgi-bin/configManager.cgi?action=getConfig&name=General.Time",
            "params": [
                {"name": "name", "type": "string", "required": True, "default": "General.Time", "desc": "配置名称"},
            ],
            "returns": {
                "format": "table",
                "fields": [
                    {"name": "table.General.Time",              "desc": "时间配置"},
                    {"name": "table.General.Time.TimeZone",     "desc": "时区"},
                    {"name": "table.General.Time.SyncType",     "desc": "同步类型（Manual/NTP）"},
                    {"name": "table.General.Time.NTPServer",    "desc": "NTP服务器地址"},
                ],
            },
        },
    ]

    # ========== 参数库扩展（新增告警/智能分析/设备管理参数） ==========

    @staticmethod
    def get_command_list():
        """返回 CGI 命令参考列表"""
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
        return [cmd for cmd in CGIReferenceManager.CGI_COMMANDS if cmd["module"] == module]

    @staticmethod
    def get_command(command_name: str) -> Optional[Dict]:
        """按命令名查询单条 CGI 命令"""
        for cmd in CGIReferenceManager.CGI_COMMANDS:
            if cmd["command"] == command_name:
                return cmd
        return None

    @staticmethod
    def get_params_by_module(module: str) -> List[Dict]:
        """查询指定模块的所有参数"""
        return [p for p in CGIReferenceManager.get_default_reference_data() if p["module"] == module]

    @staticmethod
    def search_commands(keyword: str) -> List[Dict]:
        """搜索命令（按命令名或描述模糊匹配）"""
        kw = keyword.lower()
        return [
            cmd for cmd in CGIReferenceManager.CGI_COMMANDS
            if kw in cmd["command"].lower() or kw in cmd["description"].lower()
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
        reference_file = CGIReferenceManager.get_reference_path()
        default_reference_data = CGIReferenceManager.get_default_reference_data()
        default_reference = {
            "version": "10.0",
            "last_updated": datetime.now().strftime("%Y-%m-%d"),
            "total_parameters": len(default_reference_data),
            "total_commands": len(CGIReferenceManager.CGI_COMMANDS),
            "参数库": default_reference_data,
            "CGI命令参考": CGIReferenceManager.CGI_COMMANDS,
            "模块分类": CGIReferenceManager.get_module_categories(),
        }
        try:
            if not os.path.exists(reference_file):
                CGIReferenceManager.save_reference(default_reference)
                return default_reference
            with open(reference_file, "r", encoding="utf-8") as f:
                reference = json.load(f)
            reference["version"] = "10.0"
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
        try:
            reference_file = CGIReferenceManager.get_reference_path()
            if "参数库" not in reference or not reference["参数库"]:
                reference["参数库"] = CGIReferenceManager.get_default_reference_data()
            reference["version"] = "10.0"
            reference["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            reference["total_parameters"] = len(reference.get("参数库", []))

            if "CGI命令参考" not in reference or not reference["CGI命令参考"]:
                reference["CGI命令参考"] = CGIReferenceManager.CGI_COMMANDS
            reference["total_commands"] = len(reference.get("CGI命令参考", []))

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
