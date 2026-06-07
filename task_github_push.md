# TASK: 推 GitHub — OpenClaw

## 背景
DaHua_CGI 项目 Task1-9 全部完成，全量测试 322/322 ✅
需要推送到远程 GitHub 仓库并完成集成测试。

## 先完成
### 1. 集成测试
- `src/tests/` 下有 17 个测试文件，共 322 个测试用例
- 运行：`cd /data/DaHua_CGI && /home/rzpt/.conda/envs/hermes/bin/python3 -m pytest src/tests/ -v`
- 确认全部通过

### 2. Git 操作
- `cd /data/DaHua_CGI`
- 当前状态：上一次 commit 56397e5（更新 TASKS.md），Task9 代码已提交
- 检查 `git status` 是否有未提交变更
- 如有，暂存并 commit：`git add -A && git commit -m "V9.6-alpha: GUI升级+WebUI集成"`

### 3. 推送远程
- 确认远程仓库配置：`git remote -v`
- 如无远程仓库，初始化：`git remote add origin <远程URL>`
- 推送：`git push -u origin main`

## 项目路径
- 项目：`/data/DaHua_CGI/`
- Python：`/home/rzpt/.conda/envs/hermes/bin/python3`

## 输出要求
1. 推送到远程 GitHub
2. 向 DaHua_CGI 群 @Hermes 报告结果
