# 新电脑开发接手说明

## 目的
这份文档用于在新电脑上继续开发当前项目，尤其是继续维护“AI 日报”这套二次开发能力，并支持后续继续同步上游更新。

## 先决条件
新电脑建议准备：
- Windows 10/11
- Git
- Python（建议与项目当前版本一致）
- `uv`
- Node.js / npm
- 如需桌面端打包：Visual Studio Build Tools / NSIS / Electron 打包依赖
- 如需 WCDB / 桌面运行：Microsoft Visual C++ Redistributable

## 第一步：拉代码

### 1. clone 自己的仓库
```bash
git clone https://github.com/liufeifory/WeChatDataAnalysis.git
cd WeChatDataAnalysis
```

### 2. 切到日常开发分支
如果要继续当前二开结果，优先切到：
```bash
git checkout rebase-ai-report
```

如果没有这个分支，就先看远端分支：
```bash
git branch -r
```

## 第二步：配置 upstream
为了后续继续同步原作者更新，在新电脑上也要保留 upstream：

```bash
git remote add upstream https://github.com/LifeArchiveProject/WeChatDataAnalysis.git
git fetch upstream
```

检查：
```bash
git remote -v
```

应该至少看到：
- `origin` = 自己 fork 的仓库
- `upstream` = 原作者仓库

## 第三步：安装依赖

### Python 依赖
```bash
uv sync
```

### 前端依赖
```bash
cd frontend
npm install
cd ..
```

### 桌面端依赖（如需打包 / 桌面调试）
```bash
cd desktop
npm install
cd ..
```

## 第四步：本地运行

### 启动后端
```bash
uv run main.py
```

默认端口：
- `10392`

### 启动前端开发环境
```bash
cd frontend
npm run dev
```

### 打开桌面端构建（如需要）
```bash
cd desktop
npm run dist
```

## 第五步：AI 日报相关环境变量
如果要验证 AI 日报功能，常用环境变量：

```powershell
$env:WECHAT_TOOL_DATA_DIR="<数据目录>"
$env:WECHAT_TOOL_DAILY_REPORT_DIAG_DATE="2026-04-08"
$env:WECHAT_TOOL_DAILY_REPORT_DIAG_KEYWORD="沛宇-MUJI-技术支援"
uv run main.py
```

常见变量说明：
- `WECHAT_TOOL_DATA_DIR`：运行数据目录根路径
- `WECHAT_TOOL_DAILY_REPORT_DIAG_DATE`：定点诊断日期
- `WECHAT_TOOL_DAILY_REPORT_DIAG_KEYWORD`：定点诊断群名/关键词
- `WECHAT_TOOL_PORT`：切换后端端口，避免和旧服务冲突

如果只是正常运行日报，不一定需要诊断变量。

## 第六步：日报功能验证

### 1. 语法检查
```bash
uv run -m py_compile src/wechat_decrypt_tool/daily_report_service.py src/wechat_decrypt_tool/wcdb_realtime.py
```

### 2. 单元测试
```bash
uv run -m unittest tests.test_daily_report_preserve tests.test_wcdb_realtime_time_range -v
```

### 3. 手动触发某天日报
```powershell
Invoke-WebRequest -Method POST "http://127.0.0.1:10392/api/reports/generate?date=2026-04-08"
```

### 4. 查看诊断日志
```powershell
Select-String -Path "<日志文件路径>" -Pattern "\[daily-report\]\[diag\]"
```

## 第七步：上游更新后继续二开

推荐流程：

```bash
git fetch upstream
git checkout -b rebase-ai-report-next upstream/main
git cherry-pick <AI日报代码提交>
git cherry-pick <AI日报文档提交>
```

当前已知关键提交：
- `b7be86e` — AI 日报代码提交
- `6d14286` — AI 日报文档提交
- 套到上游 `v1.17.0` 后的 replay 提交：
  - `28486b8`
  - `7bbb31c`

如果后续继续产生新的日报修复提交，也应继续按主题记录并 cherry-pick。

## 第八步：必须一起保留的仓库文档
换电脑后，优先先读这几份：
- `docs/ai-daily-report-changes.md`
- `docs/upstream-rebase-notes.md`
- `docs/new-machine-setup.md`（本文档）

它们分别解决：
- 改了什么
- 上游更新后怎么重新套回
- 新电脑怎么把环境搭起来

## 常见问题

### 1. 在错误目录运行命令
如果你在 `D:\` 根目录运行测试，会报找不到 `src/...` 或 `tests`。  
必须在项目根目录运行：
```bash
cd D:\src\WeChatDataAnalysis-1.10.0
```

### 2. 端口被占用
先查占用：
```powershell
Get-NetTCPConnection -LocalPort 10392 -State Listen | Select-Object -ExpandProperty OwningProcess
```
再结束进程：
```powershell
Stop-Process -Id <PID> -Force
```
或改端口：
```powershell
$env:WECHAT_TOOL_PORT="10932"
uv run main.py
```

### 3. 日报查不到历史群聊
先确认是否走的是：
- WCDB time-range 查询
- 或 SQLite fallback

相关逻辑已在当前二开里修过，重点看：
- `daily_report_service.py`
- `wcdb_realtime.py`

### 4. LLM 返回 402 / 余额不足
这是外部模型服务问题，不是日报链路本身错误。  
先确认：
- API Key 是否有效
- 余额是否足够
- base URL / model 是否正确

## 建议长期习惯
1. 每次功能改动后，及时写文档
2. 每次重要二开点，尽量单独 commit
3. 每次上游同步后，先跑最小回归测试
4. 不要只依赖本机环境；关键分支和文档一定要 push 到远端

## 最后建议
换电脑开发时，优先遵循：
1. 先拉代码
2. 先看文档
3. 先跑最小测试
4. 再继续改代码

这样即使几个月后再接手，也不会丢上下文。