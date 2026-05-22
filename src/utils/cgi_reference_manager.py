#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 复制自 V9.4.1/utils/cgi_reference_manager.py

import json
import os
import sys
from datetime import datetime

class CGIReferenceManager:
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
        config_dir = CGIReferenceManager.get_config_directory()
        return os.path.join(config_dir, "cgi_reference.json")

    @staticmethod
    def load_reference():
        reference_file = CGIReferenceManager.get_reference_path()
        default_reference_data = CGIReferenceManager.get_default_reference_data()
        default_reference = {
            "version": "9.2",
            "last_updated": datetime.now().strftime("%Y-%m-%d"),
            "total_parameters": len(default_reference_data),
            "参数库": default_reference_data,
            "模块分类": CGIReferenceManager.get_module_categories()
        }
        try:
            if not os.path.exists(reference_file):
                CGIReferenceManager.save_reference(default_reference)
                return default_reference
            with open(reference_file, 'r', encoding='utf-8') as f:
                reference = json.load(f)
            reference["version"] = "9.2"
            reference["last_updated"] = datetime.now().strftime("%Y-%m-%d")
            reference["total_parameters"] = len(reference.get("参数库", []))
            return reference
        except Exception:
            return default_reference

    @staticmethod
    def get_module_categories():
        return list(CGIReferenceManager.DAHUA_MODULES.keys())

    @staticmethod
    def get_default_reference_data():
        return []

    @staticmethod
    def save_reference(reference):
        try:
            reference_file = CGIReferenceManager.get_reference_path()
            if "参数库" not in reference or reference["参数库"] is None:
                reference["参数库"] = CGIReferenceManager.get_default_reference_data()
            reference["version"] = "9.2"
            reference["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            reference["total_parameters"] = len(reference.get("参数库", []))
            config_dir = os.path.dirname(reference_file)
            if not os.path.exists(config_dir):
                os.makedirs(config_dir, exist_ok=True)
            with open(reference_file, 'w', encoding='utf-8') as f:
                json.dump(reference, f, ensure_ascii=False, indent=4, sort_keys=True)
            return True
        except Exception:
            return False
