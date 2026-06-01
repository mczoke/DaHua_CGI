#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块 - V9.5
双源加载: YAML 优先, 环境变量覆盖, 兼容旧 JSON 格式
"""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError:
    yaml = None


class ConfigManager:
    """配置管理器 — 双源加载（YAML 优先, 环境变量覆盖, 兼容旧 JSON）"""

    # ========== 路径工具 ==========

    @staticmethod
    def get_app_directory() -> str:
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        else:
            return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    @staticmethod
    def get_config_directory() -> str:
        app_dir = ConfigManager.get_app_directory()
        config_dir = os.path.join(app_dir, "config")
        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
        return config_dir

    @staticmethod
    def get_config_yaml_path() -> str:
        return os.path.join(ConfigManager.get_config_directory(), "config.yaml")

    @staticmethod
    def get_config_json_path() -> str:
        return os.path.join(ConfigManager.get_config_directory(), "dahua_config.json")

    # ========== 默认值 ==========

    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        return {
            "cgi_commands": ConfigManager.get_default_cgi_commands(),
            "variable_mappings": {},
            "timeout": 30,
            "verify_ssl": False,
            "max_retries": 3,
            "auth_method": "digest",
            "ping_timeout": 3,
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

    @staticmethod
    def get_default_cgi_commands() -> List[str]:
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

    # ========== 加载 ==========

    @staticmethod
    def load_config() -> Dict[str, Any]:
        """加载配置：YAML 优先，环境变量覆盖，兼容旧 JSON"""
        defaults = ConfigManager.get_default_config()
        config: Dict[str, Any] = dict(defaults)  # 浅拷贝

        # 1) 尝试加载 YAML
        yaml_path = ConfigManager.get_config_yaml_path()
        if yaml and os.path.exists(yaml_path):
            try:
                with open(yaml_path, "r", encoding="utf-8") as f:
                    yaml_config = yaml.safe_load(f) or {}
                config.update(yaml_config)
            except Exception as e:
                logging.warning(f"加载 config.yaml 失败: {e}")

        # 2) 兼容旧 JSON（YAML 不存在的字段从 JSON 补）
        json_path = ConfigManager.get_config_json_path()
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    json_config = json.load(f)
                # JSON 覆盖 YAML（保留 YAML 中没有的字段）
                for k, v in json_config.items():
                    if k not in config or config[k] == defaults.get(k):
                        config[k] = v
            except Exception:
                pass

        # 3) 环境变量覆盖（大写 + 下划线）
        config = ConfigManager._apply_env_overrides(config)

        # 4) 校验&修正
        config = ConfigManager._validate_and_fix_config(config, defaults)

        return config

    @staticmethod
    def _apply_env_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
        """环境变量覆盖：{timeout → TIMEOUT}"""
        env_map: Dict[str, str] = {
            "timeout": "TIMEOUT",
            "ping_timeout": "PING_TIMEOUT",
            "ping_count": "PING_COUNT",
            "ping_concurrent": "PING_CONCURRENT",
            "config_concurrent": "CONFIG_CONCURRENT",
            "max_retries": "MAX_RETRIES",
            "log_level": "LOG_LEVEL",
            "export_format": "EXPORT_FORMAT",
            "auth_method": "AUTH_METHOD",
            "verify_ssl": "VERIFY_SSL",
        }
        for key, env_key in env_map.items():
            val: Optional[str] = os.environ.get(env_key)
            if val is not None:
                # 布尔/数字转换
                if val.lower() in ("true", "1", "yes"):
                    config[key] = True
                elif val.lower() in ("false", "0", "no"):
                    config[key] = False
                else:
                    try:
                        config[key] = int(val)
                    except ValueError:
                        try:
                            config[key] = float(val)
                        except ValueError:
                            config[key] = val
        return config

    @staticmethod
    def _validate_and_fix_config(
        config: Dict[str, Any], default_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        for key, value in default_config.items():
            if key not in config:
                config[key] = value
        if config.get("ping_concurrent", 0) > 200:
            config["ping_concurrent"] = 200
        if config.get("config_concurrent", 0) > 100:
            config["config_concurrent"] = 100
        return config

    # ========== 保存（写入 JSON 以保证向下兼容） ==========

    @staticmethod
    def save_config(config: Dict[str, Any]) -> bool:
        try:
            config_file = ConfigManager.get_config_json_path()
            config_dir = os.path.dirname(config_file)
            if not os.path.exists(config_dir):
                os.makedirs(config_dir, exist_ok=True)
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=4, sort_keys=True)
            return True
        except Exception:
            return False
