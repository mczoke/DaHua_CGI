Dahua CGI Tool - V9.5 (工作副本)

说明
----
这是基于 V9.4.x 的 V9.5 工作副本，包含一个异步执行器骨架（`utils/async_executor.py`）和演示/集成测试。

快捷开始（Windows PowerShell）
--------------------------------
1. 进入 V9.5 目录：

```powershell
cd 'C:\Users\Administrator\Desktop\CGI\V9.5'
```

2. 激活虚拟环境（可选，如果你已在项目根创建了 venv）：

```powershell
& 'C:\Users\Administrator\Desktop\CGI\dahua_config\Scripts\Activate.ps1'
```

3. 安装依赖（建议）：

```powershell
pip install -r .\requirements.txt
```

说明：`requirements.txt` 包含 `aiohttp`；本次版本已移除 Digest 回退实现，`aiohttp-digest-auth` 为必需依赖，请安装：

```powershell
pip install aiohttp-digest-auth
```

4. 运行演示 UI（轻量 stub）：

```powershell
python .\main.py
```

5. 运行集成测试（包含 mock CGI 服务器）：

```powershell
python .\tests\test_with_mock_server.py
python .\tests\test_stop_behavior.py
```

快速一键运行（PowerShell）：

```powershell
.\run_tests.ps1
```

文件说明
--------
- `utils/async_executor.py`：异步执行器与 `AsyncIOManager`，实现 aiohttp 请求、Digest 回退实现以及可在后台线程运行的事件循环管理。
- `utils/device_manager.py`：设备加载、检测、以及 `ConfigExecutor`（支持 `use_async=True` 的异步路径）。
- `dahua_app_stub.py`：演示 UI（已集成 `DeviceTableFrame` 和 `LogPanel` 的简化版本），绑定了开始/停止示例。
- `tests/`：集成测试和 mock CGI 服务器脚本。

当前状态 & 建议的下一步
----------------------
- 已完成：异步执行器骨架、AsyncIO 管理器、Digest 回退实现、演示 UI 的基础控件、停止/取消行为的实现与测试。
- 待做（可选）：
  - 将完整的 V9.4.1 主 UI（全部选项卡、导入/导出、设置界面）迁移到 `V9.5`。
  - 把 `ConfigExecutor` 的更多代码路径切换为异步实现并在 UI 中切换开关。
  - 在 CI 中加入测试脚本以自动验证停止行为与 Digest/Basic 路径。

Digest 支持说明
-----------------
- 代码在 `utils/async_executor.py` 中会优先使用 `aiohttp-digest-auth`（若安装）作为 Digest 认证实现。该库提供更完整的 RFC 支持（如 `nc` 递增、stale 处理以及更多算法）。
- 如果 `aiohttp-digest-auth` 未安装，代码会回退到基于 401 握手的简化实现（适用于大多数设备使用 MD5 + qop=auth 的常见情形），但并非 RFC 完整实现。
- 建议在生产环境中安装库：

```powershell
pip install aiohttp-digest-auth
```

若你希望我把回退实现替换为库依赖（直接使用库并移除回退代码），我可以在确认你愿意安装该依赖后进行。

如需我继续：我可以把完整的主界面（`V9.4.1/main.py`）有选择地迁移到 `V9.5`，并把所有控件（进度、树视图、开始/停止、导入/导出）与新的异步后端完全绑定。请确认是否继续执行完整迁移。