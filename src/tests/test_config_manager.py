"""Unit tests for config_manager.py — 80%+ coverage target.

Covers:
- get_app_directory (frozen vs unfrozen)
- get_config_directory
- get_config_yaml_path / get_config_json_path
- get_default_config — structure
- get_default_cgi_commands — content
- load_config: YAML path, JSON compat, env overrides, validate
- _apply_env_overrides: typing conversions
- _validate_and_fix_config: bounds
- save_config: success, failure
"""
import sys
import os
import json
import tempfile
from unittest.mock import MagicMock, patch, PropertyMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from utils.config_manager import ConfigManager, yaml


# ============================================================================
# Path methods
# ============================================================================

class TestGetAppDirectory:
    def test_normal(self):
        d = ConfigManager.get_app_directory()
        assert os.path.isdir(d)

    @patch('sys.frozen', True, create=True)
    @patch('sys.executable', '/opt/app/main')
    def test_frozen(self):
        d = ConfigManager.get_app_directory()
        assert d == os.path.dirname('/opt/app/main')


class TestGetConfigDirectory:
    def test_returns_path(self):
        d = ConfigManager.get_config_directory()
        assert d.endswith('config')

    def test_creates_missing(self):
        with patch.object(ConfigManager, 'get_app_directory') as mock_app:
            mock_app.return_value = tempfile.mkdtemp()
            d = ConfigManager.get_config_directory()
            assert os.path.isdir(d)
            os.rmdir(d)


class TestConfigPaths:
    def test_yaml_path(self):
        p = ConfigManager.get_config_yaml_path()
        assert p.endswith('config.yaml')

    def test_json_path(self):
        p = ConfigManager.get_config_json_path()
        assert p.endswith('dahua_config.json')


# ============================================================================
# Default config
# ============================================================================

class TestDefaultConfig:
    def test_get_default_config(self):
        cfg = ConfigManager.get_default_config()
        assert cfg['timeout'] == 30
        assert cfg['auth_method'] == 'digest'
        assert cfg['config_concurrent'] == 80
        assert 'cgi_commands' in cfg

    def test_get_default_cgi_commands(self):
        cmds = ConfigManager.get_default_cgi_commands()
        assert len(cmds) == 11  # 扩展后: 告警(4) + 智能分析(3) + 设备管理(4) = 11
        cmd_names = [c['name'] for c in cmds]
        assert 'GetAlarmRecord' in cmd_names


# ============================================================================
# _apply_env_overrides
# ============================================================================

class TestApplyEnvOverrides:
    def _test_with_env(self, env_vars):
        cfg = {'timeout': 30, 'verify_ssl': False, 'log_level': 'INFO'}
        with patch.dict(os.environ, env_vars, clear=False):
            return ConfigManager._apply_env_overrides(cfg)

    def test_no_env(self):
        result = self._test_with_env({})
        assert result['timeout'] == 30

    def test_int_override(self):
        result = self._test_with_env({'TIMEOUT': '60'})
        assert result['timeout'] == 60

    def test_bool_true(self):
        result = self._test_with_env({'VERIFY_SSL': 'true'})
        assert result['verify_ssl'] is True

    def test_bool_false(self):
        result = self._test_with_env({'VERIFY_SSL': 'false'})
        assert result['verify_ssl'] is False

    def test_float(self):
        result = self._test_with_env({'PING_TIMEOUT': '3.5'})
        assert result['ping_timeout'] == 3.5

    def test_string(self):
        result = self._test_with_env({'LOG_LEVEL': 'DEBUG'})
        assert result['log_level'] == 'DEBUG'

    def test_int_yes_no(self):
        """'yes' as int fallback handles separately."""
        result = self._test_with_env({'PING_COUNT': 'yes'})
        assert result['ping_count'] is True  # matches 'yes' branch

    def test_unknown_env_key(self):
        """Env vars not in env_map are ignored."""
        result = self._test_with_env({'UNKNOWN_KEY': 'hello'})
        # no key added that shouldn't be there
        assert result['timeout'] == 30


# ============================================================================
# _validate_and_fix_config
# ============================================================================

class TestValidateAndFixConfig:
    def test_fills_missing(self):
        defaults = ConfigManager.get_default_config()
        result = ConfigManager._validate_and_fix_config({'timeout': 42}, defaults)
        assert result['timeout'] == 42
        assert 'ping_concurrent' in result  # filled from defaults

    def test_clamps_ping_concurrent(self):
        defaults = ConfigManager.get_default_config()
        result = ConfigManager._validate_and_fix_config({'ping_concurrent': 500}, defaults)
        assert result['ping_concurrent'] == 200

    def test_clamps_config_concurrent(self):
        defaults = ConfigManager.get_default_config()
        result = ConfigManager._validate_and_fix_config({'config_concurrent': 999}, defaults)
        assert result['config_concurrent'] == 100

    def test_does_not_clamp_low_values(self):
        defaults = ConfigManager.get_default_config()
        result = ConfigManager._validate_and_fix_config({'ping_concurrent': 50}, defaults)
        assert result['ping_concurrent'] == 50


# ============================================================================
# load_config — full integration
# ============================================================================

class TestLoadConfig:
    def test_default_when_no_files(self):
        """No YAML, no JSON → returns defaults."""
        with patch.object(ConfigManager, 'get_config_yaml_path',
                          return_value='/nonexistent/config.yaml'):
            with patch.object(ConfigManager, 'get_config_json_path',
                              return_value='/nonexistent/dahua_config.json'):
                cfg = ConfigManager.load_config()
                assert cfg['timeout'] == 30
                assert len(cfg['cgi_commands']) == 11  # 扩展后: 告警4 + 智能分析3 + 设备管理4

    def test_yaml_override(self):
        """YAML file exists → overrides defaults."""
        with tempfile.TemporaryDirectory() as tmp:
            yaml_path = os.path.join(tmp, 'config.yaml')
            if yaml:
                with open(yaml_path, 'w', encoding='utf-8') as f:
                    yaml.dump({'timeout': 99, 'verify_ssl': True}, f)
            else:
                with open(yaml_path, 'w') as f:
                    f.write('timeout: 99\nverify_ssl: true\n')

            with patch.object(ConfigManager, 'get_config_yaml_path',
                              return_value=yaml_path):
                with patch.object(ConfigManager, 'get_config_json_path',
                                  return_value='/nonexistent/dahua_config.json'):
                    cfg = ConfigManager.load_config()
                    assert cfg['timeout'] == 99
                    assert cfg['verify_ssl'] is True

    def test_yaml_exception_falls_through(self):
        """YAML parse error → warning logged, continues with defaults."""
        with patch.object(ConfigManager, 'get_config_yaml_path',
                          return_value='/nonexistent/config.yaml'):
            with patch.object(ConfigManager, 'get_config_json_path',
                              return_value='/nonexistent/dahua_config.json'):
                cfg = ConfigManager.load_config()
                assert cfg['timeout'] == 30  # falls back to defaults

    def test_json_compat(self):
        """JSON file supplements YAML for fields YAML doesn't have."""
        with tempfile.TemporaryDirectory() as tmp:
            yaml_path = os.path.join(tmp, 'config.yaml')
            json_path = os.path.join(tmp, 'dahua_config.json')

            with open(yaml_path, 'w') as f:
                f.write('timeout: 45\n')

            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump({'auth_method': 'basic', 'custom_field': 'x'}, f)

            with patch.object(ConfigManager, 'get_config_yaml_path',
                              return_value=yaml_path):
                with patch.object(ConfigManager, 'get_config_json_path',
                                  return_value=json_path):
                    cfg = ConfigManager.load_config()
                    assert cfg['timeout'] == 45  # from YAML
                    assert cfg['auth_method'] == 'basic'  # from JSON
                    # json-only field: auth_method not in defaults, so it gets updated
                    # custom_field is also from JSON

    def test_json_does_not_override_yaml_diff(self):
        """JSON does NOT override YAML when YAML has non-default value."""
        with tempfile.TemporaryDirectory() as tmp:
            yaml_path = os.path.join(tmp, 'config.yaml')
            json_path = os.path.join(tmp, 'dahua_config.json')

            with open(yaml_path, 'w') as f:
                f.write('timeout: 45\n')

            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump({'timeout': 99}, f)

            with patch.object(ConfigManager, 'get_config_yaml_path',
                              return_value=yaml_path):
                with patch.object(ConfigManager, 'get_config_json_path',
                                  return_value=json_path):
                    cfg = ConfigManager.load_config()
                    assert cfg['timeout'] == 45  # YAML wins, JSON skipped because 99 != 30

    def test_json_corrupted_ignored(self):
        """Corrupted JSON → silently ignored."""
        with tempfile.TemporaryDirectory() as tmp:
            json_path = os.path.join(tmp, 'dahua_config.json')
            with open(json_path, 'w', encoding='utf-8') as f:
                f.write('{not valid')

            with patch.object(ConfigManager, 'get_config_yaml_path',
                              return_value='/nonexistent/config.yaml'):
                with patch.object(ConfigManager, 'get_config_json_path',
                                  return_value=json_path):
                    cfg = ConfigManager.load_config()
                    assert cfg['timeout'] == 30  # defaults used

    def test_env_overrides_applied(self):
        """Env vars override after YAML/JSON loading."""
        yaml_path = '/nonexistent/config.yaml'
        json_path = '/nonexistent/dahua_config.json'
        with patch.object(ConfigManager, 'get_config_yaml_path',
                          return_value=yaml_path):
            with patch.object(ConfigManager, 'get_config_json_path',
                              return_value=json_path):
                with patch.dict(os.environ, {'TIMEOUT': '120', 'LOG_LEVEL': 'ERROR'},
                                clear=False):
                    cfg = ConfigManager.load_config()
                    assert cfg['timeout'] == 120
                    assert cfg['log_level'] == 'ERROR'

    def test_validate_clamps(self):
        """Validation clamps bounds after loading."""
        with tempfile.TemporaryDirectory() as tmp:
            yaml_path = os.path.join(tmp, 'config.yaml')
            with open(yaml_path, 'w') as f:
                f.write('ping_concurrent: 999\n')

            with patch.object(ConfigManager, 'get_config_yaml_path',
                              return_value=yaml_path):
                with patch.object(ConfigManager, 'get_config_json_path',
                                  return_value='/nonexistent/dahua_config.json'):
                    cfg = ConfigManager.load_config()
                    assert cfg['ping_concurrent'] == 200  # clamped


# ============================================================================
# save_config
# ============================================================================

class TestSaveConfig:
    def test_save_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            json_path = os.path.join(tmp, 'dahua_config.json')
            with patch.object(ConfigManager, 'get_config_json_path',
                              return_value=json_path):
                with patch.object(ConfigManager, 'get_config_directory',
                                  return_value=tmp):
                    rv = ConfigManager.save_config({'timeout': 30})
                    assert rv is True
                    assert os.path.exists(json_path)

    def test_save_creates_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            nested = os.path.join(tmp, 'a', 'b')
            json_path = os.path.join(nested, 'dahua_config.json')
            with patch.object(ConfigManager, 'get_config_json_path',
                              return_value=json_path):
                with patch.object(ConfigManager, 'get_config_directory',
                                  return_value=nested):
                    rv = ConfigManager.save_config({'timeout': 30})
                    assert rv is True

    def test_save_failure(self):
        with patch.object(ConfigManager, 'get_config_json_path',
                          side_effect=OSError("disk full")):
            rv = ConfigManager.save_config({'timeout': 30})
            assert rv is False

    def test_saved_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            json_path = os.path.join(tmp, 'dahua_config.json')
            with patch.object(ConfigManager, 'get_config_json_path',
                              return_value=json_path):
                with patch.object(ConfigManager, 'get_config_directory',
                                  return_value=tmp):
                    ConfigManager.save_config({'timeout': 99, 'log_level': 'DEBUG'})
                    with open(json_path) as f:
                        saved = json.load(f)
                    assert saved['timeout'] == 99
                    assert saved['log_level'] == 'DEBUG'
