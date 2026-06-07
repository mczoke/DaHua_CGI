# TASK: Web UI 构建 — Claw-CodeX

## 背景
DaHua_CGI 项目是一个大华摄像头 CGI 批量配置工具，使用 Python 后端。
当前只有 Tkinter GUI（`src/full_app.py`），需要同步构建一个 Web 版界面。

## 项目结构
```
/data/DaHua_CGI/
├── src/
│   ├── utils/
│   │   ├── async_executor.py    # 异步执行器
│   │   ├── config_manager.py    # 配置管理
│   │   ├── device_manager.py    # 设备管理（DeviceLoader/DeviceDetector/ConfigExecutor）
│   │   ├── log_manager.py       # 日志管理
│   │   └── aggregate_collector.py # 聚合报表（Task9新增）
│   ├── config/
│   │   └── config.yaml          # 主配置
│   ├── tests/                   # 测试目录
│   └── full_app.py              # 现有 GUI（参考）
├── docs/api/                    # API 文档
├── venv/                        # 虚拟环境
└── requirements.txt
```

## 技术选型建议
- **Web框架**：Flask（轻量，与项目 python 生态一致）
- **前端**：HTML + JS（Bootstrap 5 或 Pure CSS）+ Fetch API
- **异步**：现有 `asyncio` 执行器通过线程包装（GUI 已证实可行）

## 需要构建的 Web UI 功能

### 1. 设备管理页
- 上传 Excel 加载设备列表（参考 DeviceLoader）
- 展示设备表格（IP/端口/状态/选中）
- 全选/反选/选在线
- Ping 检测（调用 DeviceDetector）

### 2. 配置执行页
- 选择设备 + 选择 CGI 命令
- 执行策略选择（device_first / command_first）
- 显示执行进度
- 显示执行结果

### 3. 聚合报表页
- 执行完成后展示 AggregatedReport
- 按设备维度 / 命令维度统计
- 导出 CSV/Excel

### 4. 配置管理页
- 查看/编辑配置参数
- 保存配置到 config.yaml

### 5. 日志查看页
- 查看运行日志

## 实现约束
- **不要改动现有 `src/utils/` 下的模块** — 直接复用
- 新增文件放在 `src/web/` 目录下
- 使用 Flask 内建服务器（无需 nginx）
- 启动脚本：`python src/web/app.py`

## 项目路径与命令
- 项目：`/data/DaHua_CGI/`
- Python：`/home/rzpt/.conda/envs/hermes/bin/python3`
- pip：`/home/rzpt/.conda/envs/hermes/bin/pip`

## 输出要求
1. 创建 `src/web/` 目录（含 `app.py` + 模板 `templates/` + 静态文件 `static/`）
2. 更新 `requirements.txt`（添加 flask）
3. 更新 `CHANGELOG.md`（新增 Web UI 条目）
4. 安装依赖后能启动 `python src/web/app.py`
5. 完成后向 DaHua_CGI 群 @Hermes 报告
