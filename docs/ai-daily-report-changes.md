# AI 日报二次开发变更清单

## 上游背景
- 本项目基于 `https://github.com/LifeArchiveProject/WeChatDataAnalysis` 做二次开发。
- 当前本地仓库远端为：`https://github.com/liufeifory/WeChatDataAnalysis.git`
- 当前可见本地基线提交：`e8478ab chore(release): bump version to 1.10.0`
- 建议后续补充记录：从上游仓库开始二开的具体 commit hash / tag。这个信息对以后再次套回上游更新非常关键。

## 二开目标
本轮二开核心目标是增加“AI 日报”能力，并围绕日报生成链路修复历史消息查询、批量生成、手工条目保留、LLM 分类与调试能力。

## 主要新增能力

### 1. AI 日报主功能
新增按天生成的 AI 日报能力：
- 扫描某天聊天记录
- 判断哪些会话应纳入日报
- 调用 OpenAI-compatible LLM 提炼摘要
- 将日报保存到本地 JSON 文件

主要文件：
- `src/wechat_decrypt_tool/daily_report_service.py`
- `src/wechat_decrypt_tool/routers/daily_reports.py`
- `src/wechat_decrypt_tool/api.py`

### 2. 日报 API
新增日报相关接口，包括：
- 列出日报日期
- 获取今日日报 / 指定日期日报
- 手动触发生成
- 批量生成
- 更新日报条目
- 添加自定义条目

主要文件：
- `src/wechat_decrypt_tool/routers/daily_reports.py`

### 3. 调度生成
增加日报调度器，支持按配置时间自动生成日报。

主要文件：
- `src/wechat_decrypt_tool/daily_report_service.py`
- `src/wechat_decrypt_tool/api.py`

## 关键改动说明

### A. 手工登记条目保留
问题：重新生成日报会覆盖手工登记内容。  
修复：
- 自定义条目写入时增加 `_is_manual` 标记
- 重新生成日报时保留旧报告中的手工条目
- 兼容旧数据：`username` 为空的历史手工条目也保留

主要文件：
- `src/wechat_decrypt_tool/routers/daily_reports.py`
- `src/wechat_decrypt_tool/daily_report_service.py`

### B. 批量生成修复
问题：批量生成会卡住、提前结束或部分日期未实际生成。  
修复：
- 批量任务改为持有强引用，避免异步任务被回收
- 修复 `_generating_lock` 与批量生成内部调用冲突
- 前端轮询不再设置过短超时导致误判“已完成部分”

主要文件：
- `src/wechat_decrypt_tool/routers/daily_reports.py`
- `frontend/pages/reports.vue`

### C. 历史日报消息查询修复（WCDB）
问题：WCDB 原来只拿最近 200 条消息，再本地筛日期；历史日期在高活跃群会被截断。  
修复过程分两步：
1. 先用翻页方案绕过“最近 200 条”限制
2. 再新增时间范围查询接口，直接按某天查询消息

最终结果：
- 新增 `wcdb_realtime.get_messages_by_time(...)`
- 日报 WCDB 路径优先按时间范围查询
- fallback 时仍可退回旧分页方案

主要文件：
- `src/wechat_decrypt_tool/wcdb_realtime.py`
- `src/wechat_decrypt_tool/daily_report_service.py`

### D. SQLite fallback 参与判定优化
问题：WCDB 不可用时，SQLite fallback 会把“当天有本人发言”的群误判成 `no replies`。  
修复：
- 从单纯依赖 `real_sender_id == my_rowid`，改为更正式的 SQL JOIN `Name2Id` 判定
- 先用 SQL 判断当天该会话是否存在本人发言
- 再取当天完整消息用于摘要
- Python 仍保留 sender 兜底识别能力

主要文件：
- `src/wechat_decrypt_tool/daily_report_service.py`

### E. 日报口径从“客户沟通”扩展为“工作日报”
原始定义偏“客户沟通日报”，会把内部技术支援群、运维排障群、项目实施群误判为非日报内容。  
已调整方向：
- 扩展 prompt 为“工作日报”
- 将内部技术支援、项目协作、运维处理、故障排查、数据库/部署/配置等内容纳入
- 增加强规则词，要求模型不要因为“内部群”直接判 false

主要文件：
- `src/wechat_decrypt_tool/daily_report_service.py`

### F. 定点诊断日志能力
为定位日报链路问题，加入了定点诊断日志：
- 指定日期
- 指定群名/关键词
- 观察 WCDB / SQLite 走哪条路径
- 看是否识别本人发言
- 看 LLM 返回内容
- 看 merge 是否吞掉结果

主要文件：
- `src/wechat_decrypt_tool/daily_report_service.py`

相关环境变量：
- `WECHAT_TOOL_DAILY_REPORT_DIAG_DATE`
- `WECHAT_TOOL_DAILY_REPORT_DIAG_KEYWORD`

## 新增/重点修改文件清单

### 新增或核心新增模块
- `src/wechat_decrypt_tool/daily_report_service.py`
- `src/wechat_decrypt_tool/routers/daily_reports.py`
- `tests/test_daily_report_preserve.py`
- `tests/test_wcdb_realtime_time_range.py`

### 重点修改文件
- `src/wechat_decrypt_tool/api.py`
- `src/wechat_decrypt_tool/wcdb_realtime.py`
- `frontend/pages/reports.vue`
- `src/wechat_decrypt_tool/chat_helpers.py`（日报复用了部分现有 helper）

## 当前已确认有效的修复点
- 手工日报条目不会在重生成时丢失
- 历史日期日报不再受 WCDB 最近 200 条窗口限制
- `get_messages_by_time()` 已能按时间范围读取某天消息
- 目标历史群聊可被正确查到并进入日报生成链路
- 批量生成链路较之前稳定

## 当前仍需注意的地方
- LLM 对“是否应计入工作日报”的分类仍可能过于保守，需要继续通过 prompt 或规则兜底优化
- WCDB `open_account` 偶发超时会触发 SQLite fallback，升级上游后要重点复测这条链路
- SQLite fallback 依赖 `Name2Id` 与 sender 解析，升级后要重点复测参与判定

## 建议后续维护方式
1. 每次继续二开时，先更新这份清单
2. 每次上游同步后，优先回归：
   - 日报生成
   - 手工条目保留
   - WCDB 历史日期查询
   - SQLite fallback
   - LLM 调用
3. 若后续继续加规则兜底，请单独记录为“规则层判断”，不要和 LLM prompt 改动混在一起
