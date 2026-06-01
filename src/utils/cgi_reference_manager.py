#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# V9.5 - 完善版: 参数库非空默认值 + 模块分类填充

import json
import logging
import os
import sys
from datetime import datetime


class CGIReferenceManager:
    """CGI 参数引用管理器 — 提供参数库、模块分类等参考数据"""

    # ========== 模块定义 ==========

    DAHUA_MODULES = {
        "VideoWidget": "视频叠加/OSD 配置",
        "ChannelTitle": "通道标题",
        "VideoBoundary": "视频边界",
        "RecordMode": "录像模式",
        "Encode": "编码参数",
        "System": "系统设置",
        "Network": "网络设置",
        "Storage": "存储设置",
    }

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

    # ========== 参数库 ==========

    @staticmethod
    def get_default_reference_data():
        """返回非空默认参数库"""
        return [
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

    @staticmethod
    def get_module_categories():
        return list(CGIReferenceManager.DAHUA_MODULES.keys())

    # ========== 加载 / 保存 ==========

    @staticmethod
    def load_reference():
        reference_file = CGIReferenceManager.get_reference_path()
        default_reference_data = CGIReferenceManager.get_default_reference_data()
        default_reference = {
            "version": "9.5",
            "last_updated": datetime.now().strftime("%Y-%m-%d"),
            "total_parameters": len(default_reference_data),
            "参数库": default_reference_data,
            "模块分类": CGIReferenceManager.get_module_categories(),
        }
        try:
            if not os.path.exists(reference_file):
                CGIReferenceManager.save_reference(default_reference)
                return default_reference
            with open(reference_file, "r", encoding="utf-8") as f:
                reference = json.load(f)
            reference["version"] = "9.5"
            reference["last_updated"] = datetime.now().strftime("%Y-%m-%d")

            # 确保参数库非空
            params = reference.get("参数库", [])
            if not params:
                params = list(default_reference_data)
                reference["参数库"] = params
            reference["total_parameters"] = len(params)

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
            reference["version"] = "9.5"
            reference["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            reference["total_parameters"] = len(reference.get("参数库", []))
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
