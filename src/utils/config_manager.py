#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 复制自 V9.4.1/utils/config_manager.py

import json
import os
import sys
from datetime import datetime

class ConfigManager:
    @staticmethod
    def get_app_directory():
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        else:
            return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    @staticmethod
    def get_config_directory():
        app_dir = ConfigManager.get_app_directory()
        config_dir = os.path.join(app_dir, "config")
        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
        return config_dir

    @staticmethod
    def get_config_path():
        config_dir = ConfigManager.get_config_directory()
        return os.path.join(config_dir, "dahua_config.json")

    @staticmethod
    def load_config():
        config_file = ConfigManager.get_config_path()
        default_config = {
            "cgi_commands": ConfigManager.get_default_cgi_commands(),
            "variable_mappings": {},
            "timeout": 1000,
            "verify_ssl": False,
            "max_retries": 0,
            "auth_method": "digest",
            "ping_timeout": 200,
            "ping_count": 1,
            "ping_concurrent": 150,
            "config_concurrent": 80,
            "exec_strategy": "device_first",
            "enable_precheck": True,
            "auto_skip_offline": True,
            "default_mode": "standard",
            "log_level": "INFO",
            "auto_save_results": True,
            "export_format": "excel",
        }
        try:
            if not os.path.exists(config_file):
                ConfigManager.save_config(default_config)
                return default_config
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            config = ConfigManager._validate_and_fix_config(config, default_config)
            return config
        except Exception:
            return default_config

    @staticmethod
    def _validate_and_fix_config(config, default_config):
        for key, value in default_config.items():
            if key not in config:
                config[key] = value
        if config.get("ping_concurrent", 0) > 200:
            config["ping_concurrent"] = 200
        if config.get("config_concurrent", 0) > 100:
            config["config_concurrent"] = 100
        return config

    @staticmethod
    def get_default_cgi_commands():
        return [
            "VideoWidget[0].CustomTitle[0].EncodeBlend=true",
            "VideoWidget[0].CustomTitle[0].PreviewBlend=true",
            "VideoWidget[0].CustomTitle[0].Rect[0]=5207",
            "VideoWidget[0].CustomTitle[0].Rect[1]=6631",
            "VideoWidget[0].CustomTitle[0].Rect[2]=7828",
            "VideoWidget[0].CustomTitle[0].Rect[3]=7069",
            "VideoWidget[0].CustomTitle[0].Text=日照职业技术学院天台山校区",
            "VideoWidget[0].CustomTitle[0].TextAlign=2",
        ]

    @staticmethod
    def save_config(config):
        try:
            config_file = ConfigManager.get_config_path()
            config_dir = os.path.dirname(config_file)
            if not os.path.exists(config_dir):
                os.makedirs(config_dir, exist_ok=True)
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4, sort_keys=True)
            return True
        except Exception:
            return False
