# 上游同步 / 再次二开说明

## 目的
这份文档用于未来同步上游 `LifeArchiveProject/WeChatDataAnalysis` 更新时，快速识别本项目 AI 日报二开改动的位置、边界和回放顺序，便于再次二次开发。

## 上游同步前必须先记录
在真正开始同步上游前，请先补齐这几个信息：
- Upstream 仓库 URL
- 当前 fork 同步上游时所基于的 commit / tag
- 本地二开开始时对应的上游 commit / tag
- 本轮二开完成时的本地 commit 列表

如果缺少这些信息，后续很难精确判断哪些是上游变更、哪些是本地二开改动。

## 二开边界
本项目 AI 日报相关改动，主要集中在以下区域：

### 高度集中区域
- `src/wechat_decrypt_tool/daily_report_service.py`
- `src/wechat_decrypt_tool/routers/daily_reports.py`
- `src/wechat_decrypt_tool/api.py`

### 关联能力区域
- `src/wechat_decrypt_tool/wcdb_realtime.py`
- `src/wechat_decrypt_tool/chat_helpers.py`
- `frontend/pages/reports.vue`
- `tests/test_daily_report_preserve.py`
- `tests/test_wcdb_realtime_time_range.py`

这些文件是以后同步上游时最容易发生冲突、也是最需要人工复核的地方。

## 建议同步策略

### 方案 A：先同步上游，再手工回放日报模块
适用情况：
- 上游改动较大
- 本地 AI 日报功能希望保持独立边界

建议步骤：
1. 从上游更新代码到新分支
2. 先解决基础冲突，不急着恢复日报功能
3. 根据 `docs/ai-daily-report-changes.md` 手工重新回放日报能力
4. 逐步恢复：
   - `daily_report_service.py`
   - `daily_reports.py`
   - `api.py` router 注册
   - `wcdb_realtime.py` 的 time-range 扩展
   - 前端 reports 页逻辑
5. 跑回归测试

优点：
- 更干净
- 不容易把旧 bug 一起带回去

### 方案 B：git cherry-pick / rebase 保留本地提交
适用情况：
- 本地日报改动已经按主题拆好 commit
- 上游改动较小

建议提交主题至少拆成：
- AI 日报主体功能
- 手工条目保留
- 批量生成修复
- WCDB 历史日期 time-range 查询
- SQLite fallback 修复
- prompt / LLM 规则调整
- 调试日志能力

优点：
- 保留开发历史
- 便于回退单个主题

## 上游同步时优先复核项

### 1. `daily_report_service.py`
重点复核：
- 是否仍能正常导入依赖
- 调度器生命周期是否还挂在 `api.py`
- prompt 是否被覆盖
- 手工条目保留逻辑是否还存在
- WCDB / SQLite 双路径是否还能正常工作

### 2. `wcdb_realtime.py`
这是高风险文件。重点复核：
- `get_messages(...)` 是否被上游改签名
- `exec_query(...)` 是否仍可用
- 新增的 `get_messages_by_time(...)` 是否还能依赖现有结构
- `WCDBRealtimeConnection` 是否还保留 `db_storage_dir`
- sidecar / native 绑定是否有变动

### 3. `chat_helpers.py`
重点复核：
- `_resolve_msg_table_name()` 是否改动
- sender 解析 helper 是否改名或挪动
- `_should_keep_session()` 规则是否改动

### 4. `frontend/pages/reports.vue`
重点复核：
- 批量生成轮询逻辑
- 停止按钮 / 进度显示
- 手工条目编辑与展示
- 日期切换逻辑

### 5. `api.py`
重点复核：
- 是否仍注册日报 router
- 启动/关闭时是否仍启动 scheduler

## 冲突优先级建议
当上游更新后，优先按下面顺序排：

1. **运行链路冲突**
- `api.py`
- `daily_report_service.py`
- `wcdb_realtime.py`

2. **数据正确性冲突**
- `chat_helpers.py`
- sender 识别 / Name2Id / message table 相关逻辑

3. **前端交互冲突**
- `frontend/pages/reports.vue`

4. **调试与测试冲突**
- diagnostics 日志
- tests

## 上游同步后的最小回归清单
每次同步上游后，至少回归下面这些：

### 功能回归
- 手动生成某天日报
- 批量生成一个日期区间
- 获取今日日报 / 指定日期日报
- 重生成后手工条目仍保留

### 数据链路回归
- WCDB 实时路径：历史日期仍可取到指定日期消息
- SQLite fallback：当 WCDB 不可用时仍能生成日报
- 目标群当天有本人发言时，能进入分析链路

### LLM 回归
- LLM 配置正确时，能正常返回摘要
- LLM 失败时，日志仍可定位问题

### 前端回归
- reports 页面可正常显示
- 日期切换正常
- 批量生成进度正常

## 推荐维护习惯
1. 每次上游同步完成后，更新本文档顶部的基线信息
2. 每新增一类日报改动，都同步更新 `docs/ai-daily-report-changes.md`
3. 若以后再加“规则兜底”，单独记成一节，不要和 prompt 修改混在一起
4. 如果开始长期维护，建议增加一个 `UPSTREAM_BASELINE.md`，专门记录：
   - upstream URL
   - upstream commit
   - fork commit
   - 二开主题 commit 列表

## 当前经验总结
本轮二开已经证明：
- 把 AI 日报能力集中在少数文件，是可维护的
- `wcdb_realtime.py` 是上游同步时最敏感区域
- 历史日期查询、sender 识别、LLM 规则口径，这三块是二开后最容易被上游更新影响的点

因此以后再次二开时，优先守住这三个边界：
1. 报表入口与调度
2. 消息采集与 sender 识别
3. LLM 分类与摘要规则
