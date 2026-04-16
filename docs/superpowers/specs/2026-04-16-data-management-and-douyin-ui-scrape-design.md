# OmniScraper Pro：数据管理（清理/删除）与抖音 UI 驱动搜索抓取设计

## 背景与问题

当前系统在以下方面存在可用性与数据一致性问题：

- 任务产生的“视频/评论/报告”等结果缺少可追溯的任务批次归档，用户无法按“某次任务”一键删除该次结果。
- 现有爬虫在 DOM 不可用时会产出 mock 数据（如 `https://www.douyin.com/video/mock_9`），造成误导并污染数据库。
- 用户需要在 UI 中清理历史报告内容、按视频删除、按任务批次删除、以及一键删除全部结果。

本设计文档定义生产级的数据模型、后端 API 与前端 UI，以实现“可控删除”和“真实 UI 路径抓取”。

## 目标

- 数据管理能力
  - 支持清空历史报告内容（保留行，不删除视频/评论/summary 行本身）。
  - 支持按任务批次删除该次任务产生的结果数据。
  - 支持按视频 ID 删除该视频的全部数据（全局删除）。
  - 支持“一键删除全部任务结果”（删除所有 task runs 及其产出）。
  - 删除操作走后端事务，失败回滚；前端提供弹窗确认。
- 抖音抓取改造
  - 采用 UI 驱动搜索：从 `https://www.douyin.com/` 首页进入，通过页面交互触发搜索并进入结果页采集。
  - 移除 mock fallback：DOM 超时/登录墙等情况不再产出 mock URL，而是明确失败并返回空结果。
  - 关键阶段可观测：通过 WS 日志输出关键步骤与错误原因。

## 非目标

- 不实现抖音接口逆向/签名级抓取（仅 UI 驱动）。
- 不实现前端直连 SQLite（仅支持后端 API）。
- 不引入复杂的权限系统（保持与当前项目一致；但会提供防误触确认）。

## 现状概览（简述）

- 数据库表：`videos`、`threads`、`summaries`。
- 抖音爬虫：现阶段可能拼接 `/search/{keyword}` 并在 DOM 不可用时返回 mock 数据。
- 前端：有“历史报告”弹窗，但缺少数据管理入口。

## 设计一：数据模型（TaskRun 归档）

### 新增表：task_runs

用途：标记“每次用户点击新建任务”对应的一次执行批次。

字段建议：

- `id`：自增主键
- `created_at`
- `platform`
- `keyword`
- `depth`
- `config_json`：保存任务配置快照（如 LLM/VLM/base_url/timeout 等，按需）
- `status`：`running | success | failed`

### 新增表：task_run_videos

用途：记录某次 run 实际处理了哪些视频，用于按 run 删除。

- `id`
- `run_id`（FK task_runs.id）
- `video_id`（FK videos.id）

### 现有表增字段

- `threads.run_id`：FK task_runs.id
- `summaries.run_id`：FK task_runs.id

说明：`videos` 不强制加入 `run_id`，因为同一视频可能被多次 run 处理。run 与 video 使用关联表 `task_run_videos` 表达。

### 删除语义（关键约定）

- 按任务批次删除（DELETE task run）
  - 删除：`task_run_videos(run_id=...)`、`threads(run_id=...)`、`summaries(run_id=...)`、`task_runs(id=...)`
  - 默认不删除 `videos`（避免误删被其它 run 引用的视频实体）
- 按视频删除（DELETE video）
  - 删除该视频的“全局全部数据”：`videos(id=...)`、`threads(video_id=...)`、`summaries(video_id=...)`、以及 `task_run_videos(video_id=...)`

## 设计二：后端 API

### 2.1 清空历史报告内容（保留行）

`POST /api/admin/reports/clear`

- 行为：对所有 summaries 执行字段清空（不删除行）：
  - `report_markdown = NULL`
  - `key_points_json = '[]'`
  - `actionable_insights = NULL`
  - `model_name = 'unknown'`（或保留；实现中统一置为 unknown）
- 返回：影响行数 `cleared_count`
- 日志：WS 广播 `"[ADMIN] 已清空 X 条报告内容"`

### 2.2 任务批次列表

`GET /api/task-runs?limit=20`

返回字段建议：

- `id / created_at / platform / keyword / depth / status`
- 统计字段（可通过 SQL 聚合或运行时计算）：
  - `video_count`（task_run_videos）
  - `thread_count`（threads）
  - `summary_count`（summaries）

### 2.3 按任务批次删除（删除该批次结果）

`DELETE /api/task-runs/{run_id}`

- 事务处理：
  - 删除 task_run_videos
  - 删除 threads（run_id）
  - 删除 summaries（run_id）
  - 删除 task_runs（id）
- 返回：删除计数（各表分别）
- 日志：WS 广播阶段性进度与最终结果

### 2.4 一键删除全部任务结果

`DELETE /api/task-runs`

- 事务处理：
  - 删除全部 task_run_videos
  - 删除全部 threads（存在 run_id 的）
  - 删除全部 summaries（存在 run_id 的）
  - 删除全部 task_runs
- 返回：删除计数
- 日志：WS 广播最终结果

### 2.5 按视频删除（全局删除）

`DELETE /api/videos/{video_id}`

- 事务处理（按视频全量清理）：
  - 删除 threads（video_id）
  - 删除 summaries（video_id）
  - 删除 task_run_videos（video_id）
  - 删除 videos（id）
- 返回：删除计数
- 日志：WS 广播最终结果

### 错误处理与一致性

- 所有删除/清空接口必须使用数据库事务，异常则 rollback 并返回错误。
- API 返回结构化 JSON，前端可提示用户“已删除/失败原因”。
- 允许后端在删除时进行基本存在性校验：run_id/video_id 不存在则返回 404 语义（或 200 + deleted=0，二选一；实现阶段确定）。

## 设计三：前端 UI（数据管理入口）

新增“数据管理”入口（建议在 header 右侧按钮区，靠近“历史报告/全局设置”）。

### 3.1 数据管理弹窗功能区块

- A. 清理报告内容
  - 按钮：`清空所有报告内容（保留视频/评论/summary 行）`
  - 点击弹窗确认后调用：`POST /api/admin/reports/clear`
- B. 任务批次管理
  - 列表：展示最近 N 次任务（run_id、时间、关键词、产出统计）
  - 每条按钮：`删除该任务结果`（DELETE /api/task-runs/{run_id}）
  - 顶部按钮：`一键删除全部任务结果`（DELETE /api/task-runs）
- C. 按视频删除入口
  - 在“历史报告”列表每条报告旁增加按钮：`删除该视频全部数据`
  - 点击弹窗确认后调用：`DELETE /api/videos/{video_id}`

### 3.2 确认方式（防误触）

用户选择：仅弹窗确认（不要求输入 DELETE）。

弹窗内容必须明确：

- 将删除哪些表/哪些数据范围
- 删除是不可逆操作
- 提供“确认/取消”

## 抖音抓取改造：UI 驱动搜索（移除 mock）

### 流程（方案 1）

1. `goto("https://www.douyin.com/")`
2. 等待首页关键元素就绪（搜索框或可输入元素）
3. 输入关键词并触发搜索（回车或点击搜索按钮）
4. 等待进入搜索结果页（通过 URL 变化或结果容器出现判断）
5. 解析结果列表卡片，提取 Top N 视频的 URL/标题/作者（以及必要的 id）
6. 逐条进入视频页抓取评论

### 失败策略（移除 mock）

- DOM 超时、登录墙、验证码、滑块等导致无法获得搜索结果：
  - 返回空列表
  - WS 广播明确错误：如 `"[ERROR] 搜索结果页不可用（登录墙/DOM 超时），未抓取到视频"`
- 不再生成任何 `mock_*` URL 或“兜底假视频”，避免污染数据库与误导用户。

### 可观测性

WS 日志至少包含：

- `[INFO] 打开抖音首页...`
- `[INFO] 输入关键词并触发搜索...`
- `[INFO] 搜索结果页就绪，开始解析视频卡片...`
- `[SUCCESS] 找到 N 个视频...`
- `[ERROR] 登录墙/DOM 超时/验证码...`（明确原因）

## 测试策略（实现阶段落地）

- 单元测试
  - 删除接口：构造视频/线程/summary/run/run_videos 数据，验证删除后各表行数变化符合语义。
  - 清空报告接口：验证 summaries 行保留但字段被清空。
- 集成测试
  - 前端点击按钮 → 调用 API → 刷新列表更新（报告库/任务批次列表）。
  - 抖音抓取在不可用时不产出 mock，且 WS 日志明确。

## 迁移与兼容

- `create_tables` 将自动创建新增表与新增字段（在 SQLite 上为简化方案；实现阶段需要确认当前 ORM 的迁移策略是否允许自动加列）。
- 旧数据（无 run_id）：
  - 不参与“按任务批次删除”
  - 仍可通过“按视频删除”清理
  - “清空报告内容”可覆盖全部 summaries（无论是否有 run_id）

