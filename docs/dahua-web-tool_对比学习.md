# dahua-web-tool 对比学习报告

> 研究对象:项目根目录 `dahua-web-tool/`(Node 实现的大华 Web 管理工具)
> 对比对象:本仓库 `DaHua_CGI`(Python Flask + aiohttp)
> 范围:仅其自有代码(`server.js / dahua.js / store.js / logger.js / importer.js / gen-streams.js / public/*`);`go2rtc/` 为内置第三方流服务,非其自有代码。

## 0. 定位差异
- **我们**:Python `Flask + aiohttp`,`CGI 批量执行 / 聚合报表 / CGI 查询`,偏「执行与分析」。
- **它**:Node 原生零依赖,`实时视频预览 + 批量运维/导入`,偏「可视化与现场管理」。
- 共同底盘相同:**「浏览器 → 本地后端代理(代持凭据 + Digest)→ 摄像头 CGI」**。

## 1. 代码质量
**相同**:都分层(我们 `src/utils/*` + `src/web`;它 `dahua.js/store.js/logger.js/importer.js`);都做日志脱敏。
**不同**:
- 它**运行时零第三方依赖**(纯 Node `http/fs/zlib`,XLSX 手写解析);我们依赖 aiohttp/httpx/pandas/openpyxl。
- 我们 `app.py`(~1250 行)与它 `server.js`(801 行)都是**单体路由文件**,规模相当。
- 它**没有任何测试**;我们有 299 个 pytest 全绿 —— 为其最大隐患。
**值得学(→ 我们)**:
- 请求级日志:每请求生成 `requestId+clientIp`,用 `logger.child()` 贯穿链路。
- 访问日志:`res.on('finish')` 记录 method/path/status/duration(对应我们的 `after_request`)。
**可改进(→ 它)**:补测试;拆分过长的 `handleApi`。

## 2. 业务逻辑
**相同**:
- 都做 Digest 转发、解析大华 `key=value`。
- **两家踩过同一坑**:`setConfig` 用 `URLSearchParams` 把 `[0]` 编码成 `%5B0%5D` 导致「返回 OK 不落库」;它手动拼查询串保留中括号,我们 `device_manager._encode_set_command` 同样处理 —— 思路一致。
**不同**:
- 它:Digest 自实现(`cnonce/nc`)、多配置名回退(`LocalNormal/Time/NTP`)、`table.` 前缀剥离、添加设备自动抓通道名回填 `name`。
- 它:批量用 **SSE 流式**(逐台 + 进度条,`Promise.allSettled` 分批,失败不停);我们 `asyncio.gather` 后一次性返回。
**值得学(→ 我们)**:SSE 流式批量进度;配置名多名称回退;`table.` 前缀归一。
**可改进(→ 它)**:批量里 `saveCameras` 逐台同步写全文件,频繁 I/O,应批量/防抖。

## 3. UI 设计
**不同**:
- 它:**左侧设备列表 + 区域树 + 多选**,右侧多标签主区(单台/批量导入/批量查看/批量修改),多选 + 区域 + 分页构成「目标范围集」语义。
- 它:**移动端响应式**(≤768px:侧栏置顶、表格横滚、触控字号≥16px 防 iOS 聚焦缩放、预览压缩)。
- 我们:Bootstrap5 + Jinja 6 模板、桌面优先、多路由页,移动适配弱。
**值得学(→ 我们)**:区域/分组树 + 多选 + 目标范围计算;移动端响应;前端操作记录 + 运行日志面板。
**可改进(→ 它)**:`public/app.js` 73KB 单文件无组件化、UI 无测试。

## 4. 业务实现
**它更强/独有**:
- 实时视频预览(go2rtc + ffmpeg):H264→WebRTC / H265→MSE 硬解 / H265 无解码器→WASM 软解;主/子码流切换(按设备 localStorage 记忆);离开自动停流。
- **go2rtc 反向代理**:go2rtc 只绑 127.0.0.1,`server.js` 用 HTTP 转发 + WebSocket upgrade 裸 TCP 隧道把 `/go2rtc/*` 同源暴露 —— 设计扎实。
- 批量查看维度更全(device/system/network/video/image/time/channelTitle)。
**我们更强/独有**:聚合报表(`AggregateResultCollector`)、CGI 查询模板库、Excel 严格校验、命令级并发加速(`config_concurrent`)、跨平台 Python。
**值得学(→ 我们)**:未来若做「预览/截图」,借鉴其 go2rtc 反向代理 + WS 隧道 + 主/子码流切换。

## 5. 数据持久化 / 日志
**相同**:都用 JSON 存设备(`cameras.json` / 我们 `device_state.json`);都按天/循环写日志。
**不同**:
- 它 `logger.js`:`级别 + 按天滚动(`logs/app-YYYY-MM-DD.log`)+ 递归脱敏(覆盖 pass/token/secret/key)+ `child()/scoped()` 上下文 + 写失败仅告警不阻断 + `logger.tail(N)` API 供前端读日志。
- 它做**操作记录审计**(`records`,上限 500,`/api/records`);我们报表是「结果型」,没有「操作行为」审计。
- 它 `saveCameras` 每次保存自动同步生成 `go2rtc.json`(单一数据源 → 派生配置)。
**值得学(→ 我们)**:logger 的「请求上下文 + tail API + 递归脱敏」组合;补一层操作审计。
**可改进(→ 它)**:操作记录仅存内存(重启丢)应落盘;`cameras.json` 明文密码应加密。

## 6. 一句话结论
它更适合「**看得见 + 现场批量运维**」(实时预览、SSE 流式、区域多选、移动端、审计记录 + 完善日志上下文),是我们可以吸收的亮点;我们更擅长「**批量执行 + 分析报表 + 质量保障**(299 测试)」。两者底层 CGI/Digest/setConfig 括号编码等坑点高度一致,互相印证了正确做法。
