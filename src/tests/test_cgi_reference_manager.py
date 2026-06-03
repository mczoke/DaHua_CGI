"""Unit tests for cgi_reference_manager.py — 80%+ coverage target.

Covers:
- CGIReferenceManager static methods
- get_app_directory (frozen vs unfrozen)
- get_config_directory (exists vs not exists)
- get_reference_path
- get_default_reference_data — structure, content
- get_module_categories
- load_reference (file exists, missing, corrupted)
- save_reference (success, failure)
"""
import sys
import os
import json
import tempfile
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from unittest.mock import patch, MagicMock

from utils.cgi_reference_manager import CGIReferenceManager

# ============================================================================
# get_app_directory
# ============================================================================

class TestGetAppDirectory:
    def test_normal(self):
        """Normal (not frozen) mode: returns src/utils/../.."""
        d = CGIReferenceManager.get_app_directory()
        assert os.path.isdir(d)

    @patch('sys.frozen', True, create=True)
    @patch('sys.executable', '/usr/local/bin/app')
    def test_frozen(self):
        d = CGIReferenceManager.get_app_directory()
        assert d == os.path.dirname('/usr/local/bin/app')


# ============================================================================
# get_config_directory
# ============================================================================

class TestGetConfigDirectory:
    def test_returns_path(self):
        d = CGIReferenceManager.get_config_directory()
        assert d.endswith('config')
        assert os.path.isdir(d)

    def test_creates_missing(self):
        with patch.object(CGIReferenceManager, 'get_app_directory') as mock_app:
            mock_app.return_value = tempfile.mkdtemp()
            d = CGIReferenceManager.get_config_directory()
            assert os.path.isdir(d)
            os.rmdir(d)  # cleanup


# ============================================================================
# get_reference_path
# ============================================================================

class TestGetReferencePath:
    def test_returns_path(self):
        p = CGIReferenceManager.get_reference_path()
        assert p.endswith('cgi_reference.json')


# ============================================================================
# get_default_reference_data
# ============================================================================

class TestGetDefaultReferenceData:
    def test_non_empty(self):
        data = CGIReferenceManager.get_default_reference_data()
        assert len(data) > 10  # should be ~17 entries
        for entry in data:
            assert 'param' in entry
            assert 'module' in entry
            assert 'type' in entry

    def test_contains_expected_modules(self):
        data = CGIReferenceManager.get_default_reference_data()
        modules = {e['module'] for e in data}
        assert 'VideoWidget' in modules
        assert 'ChannelTitle' in modules
        assert 'VideoBoundary' in modules


# ============================================================================
# get_module_categories
# ============================================================================

class TestGetModuleCategories:
    def test_returns_list(self):
        cats = CGIReferenceManager.get_module_categories()
        assert len(cats) > 0
        assert 'VideoWidget' in cats


# ============================================================================
# load_reference
# ============================================================================

class TestLoadReference:
    def test_file_missing_creates_default(self):
        """When reference file doesn't exist, create default and return it."""
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(CGIReferenceManager, 'get_config_directory',
                              return_value=tmp):
                ref = CGIReferenceManager.load_reference()
                assert ref['version'] == '10.0'
                assert len(ref['参数库']) > 10
                assert len(ref['模块分类']) > 0

    def test_file_exists_parses_correctly(self):
        """When reference file exists with valid content."""
        with tempfile.TemporaryDirectory() as tmp:
            ref_path = os.path.join(tmp, 'cgi_reference.json')
            sample = {
                'version': '9.0',
                '参数库': CGIReferenceManager.get_default_reference_data()[:2],
                '模块分类': ['VideoWidget'],
            }
            with open(ref_path, 'w', encoding='utf-8') as f:
                json.dump(sample, f)

            with patch.object(CGIReferenceManager, 'get_reference_path',
                              return_value=ref_path):
                with patch.object(CGIReferenceManager, 'get_config_directory',
                                  return_value=tmp):
                    ref = CGIReferenceManager.load_reference()
                    assert ref['version'] == '10.0'
                    assert len(ref['参数库']) == 2

    def test_file_empty_params_fills_default(self):
        """When 参数库 is empty, fill with defaults."""
        with tempfile.TemporaryDirectory() as tmp:
            ref_path = os.path.join(tmp, 'cgi_reference.json')
            sample = {
                'version': '9.0',
                '参数库': [],
                '模块分类': ['VideoWidget'],
            }
            with open(ref_path, 'w', encoding='utf-8') as f:
                json.dump(sample, f)

            with patch.object(CGIReferenceManager, 'get_reference_path',
                              return_value=ref_path):
                with patch.object(CGIReferenceManager, 'get_config_directory',
                                  return_value=tmp):
                    ref = CGIReferenceManager.load_reference()
                    assert len(ref['参数库']) > 10  # filled with defaults

    def test_file_empty_categories_fills_default(self):
        """When 模块分类 is empty, fill with defaults."""
        with tempfile.TemporaryDirectory() as tmp:
            ref_path = os.path.join(tmp, 'cgi_reference.json')
            sample = {
                'version': '9.0',
                '参数库': CGIReferenceManager.get_default_reference_data()[:2],
                '模块分类': [],
            }
            with open(ref_path, 'w', encoding='utf-8') as f:
                json.dump(sample, f)

            with patch.object(CGIReferenceManager, 'get_reference_path',
                              return_value=ref_path):
                with patch.object(CGIReferenceManager, 'get_config_directory',
                                  return_value=tmp):
                    ref = CGIReferenceManager.load_reference()
                    assert len(ref['模块分类']) > 0

    def test_corrupted_json_returns_default(self):
        """Corrupted JSON file → warn and use default."""
        with tempfile.TemporaryDirectory() as tmp:
            ref_path = os.path.join(tmp, 'cgi_reference.json')
            with open(ref_path, 'w', encoding='utf-8') as f:
                f.write('not valid json{')

            with patch.object(CGIReferenceManager, 'get_reference_path',
                              return_value=ref_path):
                with patch.object(CGIReferenceManager, 'get_config_directory',
                                  return_value=tmp):
                    ref = CGIReferenceManager.load_reference()
                    assert ref['version'] == '10.0'
                    assert len(ref['参数库']) > 10

    def test_oserror_falls_back_to_default(self):
        """OSError during open() → except catches it, returns default."""
        import builtins
        with tempfile.TemporaryDirectory() as tmp:
            ref_path = os.path.join(tmp, 'cgi_reference.json')
            sample = {
                'version': '9.0',
                '参数库': [{'param': 't', 'module': 'System'}],
                '模块分类': ['System'],
            }
            with open(ref_path, 'w', encoding='utf-8') as f:
                json.dump(sample, f)

            original_open = builtins.open

            def mock_open(*args, **kwargs):
                if 'r' in (args[1] if len(args) > 1 else kwargs.get('mode', 'r')):
                    if args[0] == ref_path:
                        raise OSError("read error")
                return original_open(*args, **kwargs)

            with patch.object(CGIReferenceManager, 'get_reference_path',
                              return_value=ref_path):
                with patch.object(CGIReferenceManager, 'get_config_directory',
                                  return_value=tmp):
                    with patch('builtins.open', side_effect=mock_open):
                        ref = CGIReferenceManager.load_reference()
                        assert ref['version'] == '10.0'
                        assert len(ref['参数库']) > 10


# ============================================================================
# save_reference
# ============================================================================

class TestSaveReference:
    def test_save_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            ref_path = os.path.join(tmp, 'cgi_reference.json')
            with patch.object(CGIReferenceManager, 'get_reference_path',
                              return_value=ref_path):
                with patch.object(CGIReferenceManager, 'get_config_directory',
                                  return_value=tmp):
                    rv = CGIReferenceManager.save_reference({
                        '参数库': [{'param': 'test', 'module': 'System'}],
                        '模块分类': ['System'],
                    })
                    assert rv is True
                    assert os.path.exists(ref_path)
                    with open(ref_path) as f:
                        saved = json.load(f)
                    assert saved['version'] == '10.0'

    def test_save_fills_missing_params(self):
        """Save with missing 参数库 fills defaults."""
        with tempfile.TemporaryDirectory() as tmp:
            ref_path = os.path.join(tmp, 'cgi_reference.json')
            with patch.object(CGIReferenceManager, 'get_reference_path',
                              return_value=ref_path):
                with patch.object(CGIReferenceManager, 'get_config_directory',
                                  return_value=tmp):
                    rv = CGIReferenceManager.save_reference({})
                    assert rv is True
                    with open(ref_path) as f:
                        saved = json.load(f)
                    assert len(saved['参数库']) > 10

    def test_save_fills_missing_categories(self):
        with tempfile.TemporaryDirectory() as tmp:
            ref_path = os.path.join(tmp, 'cgi_reference.json')
            with patch.object(CGIReferenceManager, 'get_reference_path',
                              return_value=ref_path):
                with patch.object(CGIReferenceManager, 'get_config_directory',
                                  return_value=tmp):
                    rv = CGIReferenceManager.save_reference({
                        '参数库': [{'param': 't', 'module': 'S'}],
                    })
                    assert rv is True
                    with open(ref_path) as f:
                        saved = json.load(f)
                    assert len(saved['模块分类']) > 0

    def test_save_oserror(self):
        """OSError during save → False."""
        with patch.object(CGIReferenceManager, 'get_reference_path',
                          side_effect=OSError("disk full")):
            rv = CGIReferenceManager.save_reference({
                '参数库': CGIReferenceManager.get_default_reference_data(),
                '模块分类': ['System'],
            })
            assert rv is False

    def test_save_creates_dir(self):
        """Save creates config directory if missing."""
        with tempfile.TemporaryDirectory() as tmp:
            missing_dir = os.path.join(tmp, 'nonexistent', 'nested')
            ref_path = os.path.join(missing_dir, 'cgi_reference.json')
            with patch.object(CGIReferenceManager, 'get_reference_path',
                              return_value=ref_path):
                with patch.object(CGIReferenceManager, 'get_config_directory',
                                  return_value=missing_dir):
                    rv = CGIReferenceManager.save_reference({
                        '参数库': [{'param': 't', 'module': 'S'}],
                        '模块分类': ['System'],
                    })
                    assert rv is True


# ============================================================================
# CGI Commands (v10.0)
# ============================================================================

class TestCGICommands:
    """Tests for CGI command reference."""

    _MOCK_COMMANDS = [
        {"name": "GetAlarmRecord", "module": "Alarm",
         "path": "/cgi-bin/eventManager.cgi", "method": "GET",
         "auth": "digest", "timeout": 30, "description": "获取告警记录",
         "params": [{"name": "action", "type": "string",
                      "required": True, "default": "getAlarmRecord"}]},
        {"name": "GetAlarmConfig", "module": "Alarm",
         "path": "/cgi-bin/configManager.cgi", "method": "GET",
         "auth": "digest", "timeout": 30, "description": "获取告警配置",
         "params": [{"name": "action", "type": "string",
                      "required": True, "default": "getConfig"}]},
        {"name": "SetAlarmConfig", "module": "Alarm",
         "path": "/cgi-bin/configManager.cgi", "method": "GET",
         "auth": "digest", "timeout": 30, "description": "设置告警配置",
         "params": [{"name": "action", "type": "string",
                      "required": True, "default": "setConfig"}]},
        {"name": "GetEventType", "module": "Alarm",
         "path": "/cgi-bin/eventManager.cgi", "method": "GET",
         "auth": "digest", "timeout": 30, "description": "获取事件类型",
         "params": [{"name": "action", "type": "string",
                      "required": True, "default": "getEventType"}]},
    ]

    @staticmethod
    def _mock_config():
        """模拟 ConfigManager.load_config() 返回含 cgi_commands 的配置."""
        return {"cgi_commands": TestCGICommands._MOCK_COMMANDS}

    # ---- 依赖配置加载的命令测试 ----

    @patch('utils.config_manager.ConfigManager.load_config', side_effect=_mock_config)
    def test_get_command_list_nonempty(self, mock_cfg):
        CGIReferenceManager._CGI_COMMANDS_LOADED = False
        commands = CGIReferenceManager.get_command_list()
        assert len(commands) == 4
        for cmd in commands:
            assert 'name' in cmd
            assert 'module' in cmd
            assert 'method' in cmd
            assert 'path' in cmd
            assert 'description' in cmd
            assert 'params' in cmd

    @patch('utils.config_manager.ConfigManager.load_config', side_effect=_mock_config)
    def test_get_command_list_contains_new_commands(self, mock_cfg):
        CGIReferenceManager._CGI_COMMANDS_LOADED = False
        commands = CGIReferenceManager.get_command_list()
        cmd_names = {c['name'] for c in commands}
        assert 'GetAlarmRecord' in cmd_names
        assert 'GetAlarmConfig' in cmd_names
        assert 'SetAlarmConfig' in cmd_names
        assert 'GetEventType' in cmd_names

    @patch('utils.config_manager.ConfigManager.load_config', side_effect=_mock_config)
    def test_get_command_found(self, mock_cfg):
        CGIReferenceManager._CGI_COMMANDS_LOADED = False
        cmd = CGIReferenceManager.get_command('GetAlarmRecord')
        assert cmd is not None
        assert cmd['module'] == 'Alarm'

    def test_get_command_not_found(self):
        CGIReferenceManager._CGI_COMMANDS_LOADED = False
        cmd = CGIReferenceManager.get_command('NonExistentCommand')
        assert cmd is None

    @patch('utils.config_manager.ConfigManager.load_config', side_effect=_mock_config)
    def test_get_commands_by_module(self, mock_cfg):
        CGIReferenceManager._CGI_COMMANDS_LOADED = False
        alarm_cmds = CGIReferenceManager.get_commands_by_module('Alarm')
        assert len(alarm_cmds) == 4
        names = {c['name'] for c in alarm_cmds}
        assert names == {'GetAlarmRecord', 'GetAlarmConfig', 'SetAlarmConfig', 'GetEventType'}

    def test_get_commands_by_module_empty(self):
        CGIReferenceManager._CGI_COMMANDS_LOADED = False
        cmds = CGIReferenceManager.get_commands_by_module('NonExistent')
        assert cmds == []

    @patch('utils.config_manager.ConfigManager.load_config', side_effect=_mock_config)
    def test_search_commands_by_name(self, mock_cfg):
        CGIReferenceManager._CGI_COMMANDS_LOADED = False
        results = CGIReferenceManager.search_commands('Alarm')
        assert len(results) >= 3

    @patch('utils.config_manager.ConfigManager.load_config', side_effect=_mock_config)
    def test_search_commands_by_desc(self, mock_cfg):
        CGIReferenceManager._CGI_COMMANDS_LOADED = False
        results = CGIReferenceManager.search_commands('告警')
        assert len(results) >= 3

    # ---- 不依赖配置的命令测试 ----

    def test_search_params_by_name(self):
        results = CGIReferenceManager.search_params('MotionDetect')
        assert len(results) >= 1

    def test_search_params_by_desc(self):
        results = CGIReferenceManager.search_params('灵敏度')
        assert len(results) >= 2

    def test_get_params_by_module(self):
        alarm_params = CGIReferenceManager.get_params_by_module('Alarm')
        assert len(alarm_params) >= 7

    def test_params_contain_new_modules(self):
        all_params = CGIReferenceManager.get_default_reference_data()
        modules = {p['module'] for p in all_params}
        assert 'Alarm' in modules
        assert 'SmartAnalysis' in modules
        assert 'DeviceConfig' in modules

    def test_total_params_increased(self):
        params = CGIReferenceManager.get_default_reference_data()
        assert len(params) > 20

    def test_dahua_modules_extended(self):
        assert 'Alarm' in CGIReferenceManager.DAHUA_MODULES
        assert 'SmartAnalysis' in CGIReferenceManager.DAHUA_MODULES
        assert 'DeviceConfig' in CGIReferenceManager.DAHUA_MODULES

    def test_dahua_modules_total_count(self):
        assert len(CGIReferenceManager.DAHUA_MODULES) == 11

    @patch.object(CGIReferenceManager, 'get_reference_path')
    @patch.object(CGIReferenceManager, 'get_config_directory')
    @patch('utils.config_manager.ConfigManager.load_config', side_effect=_mock_config)
    def test_load_reference_includes_commands(self, mock_cfg, mock_config, mock_path):
        """load_reference should include CGI命令参考."""
        CGIReferenceManager._CGI_COMMANDS_LOADED = False
        with tempfile.TemporaryDirectory() as tmp:
            ref_path = os.path.join(tmp, 'cgi_reference.json')
            mock_path.return_value = ref_path
            mock_config.return_value = tmp
            ref = CGIReferenceManager.load_reference()
            assert 'CGI命令参考' in ref
            assert len(ref['CGI命令参考']) == 4
            assert ref['total_commands'] == 4

    @patch.object(CGIReferenceManager, 'get_reference_path')
    @patch.object(CGIReferenceManager, 'get_config_directory')
    @patch('utils.config_manager.ConfigManager.load_config', side_effect=_mock_config)
    def test_save_reference_includes_commands(self, mock_cfg, mock_config, mock_path):
        """save_reference should populate CGI命令参考."""
        CGIReferenceManager._CGI_COMMANDS_LOADED = False
        with tempfile.TemporaryDirectory() as tmp:
            ref_path = os.path.join(tmp, 'cgi_reference.json')
            mock_path.return_value = ref_path
            mock_config.return_value = tmp
            rv = CGIReferenceManager.save_reference({
                '参数库': [{'param': 't', 'module': 'S'}],
                '模块分类': ['System'],
            })
            assert rv is True
            with open(ref_path) as f:
                saved = json.load(f)
            assert 'CGI命令参考' in saved
            assert len(saved['CGI命令参考']) > 0
            assert saved['version'] == '10.0'
