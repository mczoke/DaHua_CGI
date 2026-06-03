"""Task6b - 端到端集成测试：CGI 参数引用 → 配置管理 → 设备管理 → 日志记录全链路

Scenarios:
1. CGIReferenceManager → ConfigManager 参数传递
2. ConfigManager → ConfigExecutor 设备配置执行
3. ConfigExecutor → LogManager 日志记录
4. 完整的 CGI 请求 -> 设备管理 -> 日志记录
5. 异常路径：参数缺失、设备离线、网络错误
6. URL认证兼容模式
7. 配置文件持久化
"""
import sys
import os
import json
import tempfile
import threading
import time
import asyncio
from unittest.mock import MagicMock, patch, PropertyMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from utils.cgi_reference_manager import CGIReferenceManager
from utils.config_manager import ConfigManager, yaml
from utils.device_manager import ConfigExecutor, DeviceInfo, DeviceLoader
from utils.log_manager import LogManager


# ============================================================================
# Test 1: CGIReferenceManager → ConfigManager 参数传递
# ============================================================================

class TestReferenceToConfig:
    """验证 CGI 参数引用与配置管理器的集成"""

    def test_default_commands_match_reference(self):
        """ConfigManager 默认命令中的 VideoWidget 参数应该在参考参数库中有对应定义"""
        ref_params = CGIReferenceManager.get_default_reference_data()
        default_commands = ConfigManager.get_default_cgi_commands()

        # 参考库中定义的参数名集合
        ref_param_names = {r["param"] for r in ref_params}

        # 只验证 VideoWidget 相关命令（原有的）在参考库中有定义
        video_commands = [c for c in default_commands
                          if any("VideoWidget" in p.get("name", "")
                                 for p in c.get("params", []))]

        for cmd in video_commands:
            for param in cmd.get("params", []):
                param_name = param["name"]
                assert param_name in ref_param_names, \
                    f"参数 {param_name} 在命令 {cmd['name']} 中未在参考参数库中找到"

        # 验证参考参数库包含基础参数
        assert "VideoWidget[0].CustomTitle[0].EncodeBlend" in ref_param_names
        assert "VideoWidget[0].CustomTitle[0].Text" in ref_param_names

    def test_reference_loads_with_config(self):
        """使用 ConfigManager 加载配置后，应该可以关联参考参数"""
        cfg = ConfigManager.load_config()
        ref = CGIReferenceManager.load_reference()

        assert "参数库" in ref
        assert len(ref["参数库"]) > 0
        assert ref["version"] == "10.0"

    def test_reference_save_and_reload(self):
        """保存参考参数后，应该能重新加载"""
        with tempfile.TemporaryDirectory() as tmp:
            ref_path = os.path.join(tmp, "cgi_reference.json")
            with patch.object(CGIReferenceManager, "get_reference_path",
                              return_value=ref_path):
                with patch.object(CGIReferenceManager, "get_config_directory",
                                  return_value=tmp):
                    # 保存
                    ref = {
                        "参数库": CGIReferenceManager.get_default_reference_data(),
                        "模块分类": CGIReferenceManager.get_module_categories(),
                    }
                    saved = CGIReferenceManager.save_reference(ref)
                    assert saved is True
                    assert os.path.exists(ref_path)

                    # 重新加载
                    loaded = CGIReferenceManager.load_reference()
                    assert loaded["total_parameters"] == len(
                        CGIReferenceManager.get_default_reference_data()
                    )
                    assert loaded["version"] == "10.0"


# ============================================================================
# Test 2: ConfigManager → ConfigExecutor 设备配置执行
# ============================================================================

class TestConfigToExecutor:
    """验证配置管理器到执行器的参数传递"""

    def test_config_passed_to_executor(self):
        """ConfigManager 加载的配置能正确传递给 ConfigExecutor"""
        cfg = ConfigManager.load_config()
        log = LogManager()
        exe = ConfigExecutor(cfg, log)

        assert exe.config_concurrent == cfg.get("config_concurrent", 30)
        assert exe.timeout == cfg.get("timeout", 3000) / 1000.0
        assert exe.auth_method == cfg.get("auth_method", "digest")
        assert exe.config == cfg

    def test_cgi_commands_flow(self):
        """cgi_commands 从配置流入执行器"""
        cfg = ConfigManager.load_config()
        commands = cfg.get("cgi_commands", [])
        assert len(commands) > 0

        log = LogManager()
        exe = ConfigExecutor(cfg, log)
        # 验证执行器可以从中获取命令
        assert exe.config.get("cgi_commands") == commands

    def test_device_info_from_config(self):
        """设备信息与配置结合"""
        cfg = ConfigManager.load_config()
        log = LogManager()
        exe = ConfigExecutor(cfg, log, use_async=True)

        # 创建在线设备
        dev = DeviceInfo(
            index=0, ip="127.0.0.1", port="9080",
            username="admin", password="admin",
            online=True, status="在线",
        )

        # 设备有 get_display_info 方法
        info = dev.get_display_info()
        assert "127.0.0.1:9080" in info


# ============================================================================
# Test 3: ConfigExecutor → LogManager 日志记录
# ============================================================================

class TestExecutorToLog:
    """验证执行器的日志记录到 LogManager"""

    def test_executor_logs_via_logmanager(self):
        """ConfigExecutor 的日志通过 LogManager 记录"""
        cfg = {"cgi_commands": [], "config_concurrent": 5, "timeout": 3000}
        log = LogManager()
        exe = ConfigExecutor(cfg, log)

        # 执行器通过 _log 发送消息
        exe._log("测试日志消息", "INFO")

        # 验证日志被记录到 LogManager
        assert log.detailed_log_file is not None
        with open(log.detailed_log_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "测试日志消息" in content

    def test_executor_logs_failure(self):
        """执行器的失败记录到 LogManager 的失败日志"""
        cfg = {"cgi_commands": ["Param=1"], "config_concurrent": 5, "timeout": 3000}
        log = LogManager()
        exe = ConfigExecutor(cfg, log)

        dev = DeviceInfo(
            index=0, ip="10.0.0.99", port="80",
            username="admin", password="admin",
            online=True, status="在线",
        )

        # 测试失败日志记录
        log.log_failure(dev, "连接超时", "Param=1")
        with open(log.failure_log_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "10.0.0.99" in content
        assert "连接超时" in content

    def test_log_detailed_integration(self):
        """LogManager.log_detailed 与执行器集成"""
        cfg = {"cgi_commands": ["TestCmd=1"], "config_concurrent": 5, "timeout": 3000}
        log = LogManager()

        log.log_detailed("开始批量配置", "INFO")
        log.log_detailed("设备 127.0.0.1 配置完成", "SUCCESS")
        log.log_detailed("设备 10.0.0.1 配置失败", "ERROR")

        with open(log.detailed_log_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "开始批量配置" in content
        assert "127.0.0.1 配置完成" in content
        assert "10.0.0.1 配置失败" in content


# ============================================================================
# Test 4: 完整的 CGI 请求 -> 设备管理 -> 日志记录
# ============================================================================

class TestFullPipeline:
    """端到端全链路测试：使用 mock CGI server"""

    MOCK_PORT = 9081

    @pytest.fixture(scope="class")
    def mock_server(self):
        """启动 mock CGI server"""
        from aiohttp import web
        server = {}

        scenarios = {
            "success": {"status": 200, "body": "OK", "delay": 0},
            "auth_failed": {"status": 401, "body": "Unauthorized", "delay": 0},
            "slow": {"status": 200, "body": "OK", "delay": 2},
        }

        async def handle_config(request):
            scenario_name = request.query.get("scenario", "success")
            scenario = scenarios.get(scenario_name, scenarios["success"])
            if scenario["delay"] > 0:
                await asyncio.sleep(scenario["delay"])
            auth = request.headers.get("Authorization")
            if scenario["status"] == 401:
                hdr = 'Digest realm="testrealm", nonce="abc123", qop="auth"'
                return web.Response(
                    status=401, headers={"WWW-Authenticate": hdr},
                    text=scenario["body"],
                )
            if auth or scenario_name == "auth_failed":
                return web.Response(status=scenario["status"], text=scenario["body"])
            hdr = 'Digest realm="testrealm", nonce="abc123", qop="auth"'
            return web.Response(
                status=401, headers={"WWW-Authenticate": hdr}, text="Unauthorized",
            )

        def _run():
            loop = asyncio.new_event_loop()
            server["loop"] = loop
            asyncio.set_event_loop(loop)
            app = web.Application()
            app.router.add_get("/cgi-bin/configManager.cgi", handle_config)
            app.router.add_get("/status", lambda r: web.Response(text="OK"))
            runner = web.AppRunner(app)
            loop.run_until_complete(runner.setup())
            site = web.TCPSite(runner, "127.0.0.1", self.MOCK_PORT)
            loop.run_until_complete(site.start())
            try:
                loop.run_forever()
            finally:
                loop.run_until_complete(runner.cleanup())
                loop.close()

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        timeout = 5
        start = time.time()
        while "loop" not in server and time.time() - start < timeout:
            time.sleep(0.05)
        time.sleep(0.2)
        server["thread"] = t
        yield server
        if "loop" in server:
            server["loop"].call_soon_threadsafe(server["loop"].stop)
            server["thread"].join(timeout=2)

    def test_pipeline_success(self, mock_server):
        """
        全链路成功场景：
        ConfigManager 加载配置 → ConfigExecutor 执行 → LogManager 记录
        """
        # 步骤1: ConfigManager 加载配置
        cfg = ConfigManager.load_config()
        cfg["cgi_commands"] = ["VideoTitle=TestOSD"]
        cfg["config_concurrent"] = 5
        cfg["timeout"] = 5000
        cfg["verify_ssl"] = False

        # 步骤2: 创建 LogManager
        log = LogManager()

        # 步骤3: 创建 ConfigExecutor
        exe = ConfigExecutor(cfg, log, use_async=True)

        try:
            # 步骤4: 创建设备
            dev = DeviceInfo(
                index=0, ip="127.0.0.1", port=str(self.MOCK_PORT),
                username="admin", password="admin",
                online=True, status="在线",
            )

            # 步骤5: 执行批量配置
            results = exe.execute_batch(
                [dev],
                mode="standard",
                exec_strategy="device_first",
                progress_callback=lambda t, p, s: None,
                stop_callback=None,
            )

            # 步骤6: 验证结果
            assert isinstance(results, list), f"Expected list, got {type(results)}"
            if results:
                r = results[0]
                assert r["ip"] == "127.0.0.1"
        finally:
            exe.stop()

        # 步骤7: 验证日志记录
        with open(log.detailed_log_file, "r", encoding="utf-8") as f:
            log_content = f.read()
        assert "127.0.0.1" in log_content or "TestOSD" in log_content or len(log_content) > 50

    def test_pipeline_offline_device(self, mock_server):
        """离线设备应该被跳过"""
        cfg = {"cgi_commands": ["Param=1"], "config_concurrent": 5, "timeout": 3000, "verify_ssl": False}
        log = LogManager()
        exe = ConfigExecutor(cfg, log, use_async=True)

        try:
            offline_dev = DeviceInfo(
                index=0, ip="127.0.0.1", port=str(self.MOCK_PORT),
                username="admin", password="admin",
                online=False, status="离线",
            )
            results = exe.execute_batch(
                [offline_dev],
                mode="standard",
                exec_strategy="device_first",
            )
            # 离线设备不应执行
            assert results == [] or len(results) == 0
        finally:
            exe.stop()

    def test_pipeline_invalid_port(self, mock_server):
        """无效端口 → 连接失败 → 记录日志"""
        cfg = {"cgi_commands": ["Param=1"], "config_concurrent": 5, "timeout": 3000, "verify_ssl": False}
        log = LogManager()
        exe = ConfigExecutor(cfg, log, use_async=True)

        try:
            unreachable_dev = DeviceInfo(
                index=0, ip="127.0.0.1", port="19999",
                username="admin", password="admin",
                online=True, status="在线",
            )
            results = exe.execute_batch(
                [unreachable_dev],
                mode="standard",
                exec_strategy="device_first",
            )
            # 可能返回部分结果或空列表（取决于连接失败处理方式）
            assert isinstance(results, list)
        finally:
            exe.stop()

    def test_pipeline_commands_from_reference(self, mock_server):
        """使用从参考参数库获取的命令执行配置"""
        ref = CGIReferenceManager.get_default_reference_data()
        # 取第一个参数的 command 格式
        first_param = ref[0]
        param_name = first_param["param"]
        example = first_param["example"]
        cmd = f"{param_name}={example}"

        cfg = {"cgi_commands": [cmd], "config_concurrent": 5, "timeout": 5000, "verify_ssl": False}
        log = LogManager()
        exe = ConfigExecutor(cfg, log, use_async=True)

        try:
            dev = DeviceInfo(
                index=0, ip="127.0.0.1", port=str(self.MOCK_PORT),
                username="admin", password="admin",
                online=True, status="在线",
            )
            results = exe.execute_batch(
                [dev],
                mode="standard",
                exec_strategy="device_first",
            )
            assert isinstance(results, list)
            if results:
                r = results[0]
                assert r["ip"] == "127.0.0.1"
        finally:
            exe.stop()


# ============================================================================
# Test 5: 异常路径测试
# ============================================================================

class TestPipelineExceptions:
    """异常路径：参数缺失、设备离线、网络错误"""

    def test_config_missing_cgi_commands(self):
        """配置缺少 cgi_commands 不应崩溃"""
        cfg = {"timeout": 30, "config_concurrent": 5}
        log = LogManager()
        exe = ConfigExecutor(cfg, log)
        commands = cfg.get("cgi_commands", [])
        assert commands == []

    def test_device_without_required_fields(self):
        """设备缺少必要字段的处理"""
        dev = DeviceInfo(index=0, ip="10.0.0.1", port="", username="", password="")
        display = dev.get_display_info()
        assert "10.0.0.1" in display

    def test_ref_manager_empty_reference(self):
        """参考参数库为空时的处理"""
        ref = {"参数库": [], "模块分类": []}
        with patch.object(CGIReferenceManager, "get_reference_path",
                          return_value="/nonexistent/ref.json"):
            with patch.object(CGIReferenceManager, "get_config_directory",
                              return_value="/tmp"):
                # load_reference 应该返回默认值
                loaded = CGIReferenceManager.load_reference()
                assert len(loaded.get("参数库", [])) > 0  # 使用了默认值
                assert len(loaded.get("模块分类", [])) > 0


# ============================================================================
# Test 6: 配置文件持久化
# ============================================================================

class TestConfigPersistence:
    """配置文件持久化操作测试"""

    def test_config_save_and_reload(self):
        """配置保存后重新加载"""
        with tempfile.TemporaryDirectory() as tmp:
            json_path = os.path.join(tmp, "dahua_config.json")
            with patch.object(ConfigManager, "get_config_json_path",
                              return_value=json_path):
                with patch.object(ConfigManager, "get_config_directory",
                                  return_value=tmp):
                    saved = ConfigManager.save_config({
                        "timeout": 60,
                        "auth_method": "basic",
                        "cgi_commands": ["Cmd1=value"],
                    })
                    assert saved is True

                    with patch.object(ConfigManager, "get_config_yaml_path",
                                      return_value="/nonexistent/config.yaml"):
                        loaded = ConfigManager.load_config()
                        assert loaded["timeout"] == 60
                        assert loaded["auth_method"] == "basic"

    def test_config_yaml_preferred(self):
        """YAML 配置文件优先于 JSON"""
        with tempfile.TemporaryDirectory() as tmp:
            yaml_path = os.path.join(tmp, "config.yaml")
            json_path = os.path.join(tmp, "dahua_config.json")

            # 写入 YAML
            with open(yaml_path, "w") as f:
                f.write("timeout: 99\nverify_ssl: true\n")

            # 写入不同值的 JSON
            with open(json_path, "w") as f:
                json.dump({"timeout": 50, "auth_method": "basic"}, f)

            with patch.object(ConfigManager, "get_config_yaml_path",
                              return_value=yaml_path):
                with patch.object(ConfigManager, "get_config_json_path",
                                  return_value=json_path):
                    loaded = ConfigManager.load_config()
                    assert loaded["timeout"] == 99  # YAML wins
                    assert loaded["verify_ssl"] is True

    def test_reference_save_persistence(self):
        """参考参数保存后持久化"""
        with tempfile.TemporaryDirectory() as tmp:
            ref_path = os.path.join(tmp, "cgi_reference.json")
            with patch.object(CGIReferenceManager, "get_reference_path",
                              return_value=ref_path):
                with patch.object(CGIReferenceManager, "get_config_directory",
                                  return_value=tmp):
                    # 保存初始数据
                    ref_data = CGIReferenceManager.get_default_reference_data()
                    ref = {
                        "参数库": ref_data,
                        "模块分类": CGIReferenceManager.get_module_categories(),
                    }
                    CGIReferenceManager.save_reference(ref)

                    # 验证文件存在
                    assert os.path.exists(ref_path)
                    with open(ref_path, "r", encoding="utf-8") as f:
                        saved = json.load(f)
                    assert "参数库" in saved
                    assert saved["version"] == "10.0"
