# OmniScraper Pro Phase 4: 真实平台爬虫接入设计 (Spec)

## 1. 目标与范围 (Scope)

在已完成的 DB 基础、多模态/LLM 闭环以及 FastAPI+WebSocket 的通信基础上，Phase 4 旨在引入真实的浏览器自动化工具 (Playwright)，实现对真实平台（首发目标：抖音）的视频列表及评论数据的自动化无头抓取。

**核心目标：**
1. 构建通用的爬虫基类 (`BaseScraper`) 与工厂模式。
2. 实现基于 Playwright 的抖音爬虫 (`DouyinScraper`)。
3. 结合 Phase 1 的防风控中间件 (`AntiBotController`)，在搜索和翻页操作时加入拟人化随机延迟。
4. 将真实的抓取数据存入 SQLite 并对接已有的 AnalysisPipeline 触发总结。

**设计原则：**
- **MVP 策略**：由于复杂的风控与登录墙，第一版真实爬虫主要针对公开无需登录的内容（如搜索结果前几项及部分公开评论），重点在于打通代码结构和全链路的数据落库。如果触发滑块验证或强制登录，我们在此阶段选择“静默忽略并返回当前已抓取数据”，以便完成链路。
- **可插拔**：爬虫模块应该独立，返回标准字典格式，交由调用方（`main.py`）统一入库。

## 2. 架构与模块划分

### 2.1 爬虫接口设计 (`backend/scrapers/base.py`)

*   **`BaseScraper`**: 抽象基类。
    *   `start_browser()`: 初始化 Playwright 引擎，启动浏览器上下文，注入抗指纹脚本（如需要）。
    *   `close_browser()`: 优雅释放资源。
    *   `search_videos(keyword: str, max_count: int) -> List[dict]`: 执行关键词搜索，返回视频元数据。
    *   `fetch_comments(video_url: str, max_depth: int) -> List[dict]`: 抓取单个视频的一级与二级评论（树状结构或平铺后在外部组装）。

### 2.2 抖音爬虫实现 (`backend/scrapers/douyin.py`)

*   **`DouyinScraper`**: 继承自 `BaseScraper`。
    *   内部实例化 `AntiBotController`。
    *   `search_videos`：导航至 `https://www.douyin.com/search/{keyword}`，使用 Playwright 的 `locator` 等待视频卡片加载，解析标题、作者、URL 和点赞数。并在循环中加入 `anti_bot.random_delay("search")`。
    *   `fetch_comments`：导航至视频播放页，定位评论区容器，滚动加载。为了防封号，滚动间加入 `anti_bot.random_delay("scroll_comments")`。

### 2.3 调度集成 (`backend/main.py`)

*   修改 `mock_pipeline_execution`：
    *   将其改名为 `run_real_pipeline`。
    *   使用 `DouyinScraper` 进行真实抓取。
    *   将抓取结果写入 SQLite（`Video` 和 `Thread` 表）。
    *   触发 `AnalysisPipeline`。
    *   通过 `manager.broadcast` 实时反馈抓取与分析进度给 React 前端。

## 3. 数据结构规约

爬虫提取的数据需遵循以下最小集合，以便平滑写入 ORM：

**视频元数据 (Video dict):**
```json
{
  "id": "123456789",          // 平台视频ID
  "platform": "douyin",
  "url": "https://...",
  "title": "视频标题",
  "author": "作者昵称",
  "like_count": 1000
}
```

**评论数据 (Thread dict):**
```json
{
  "root_comment": "这视频太棒了！",
  "replies": ["确实", "赞同"]     // 简单转换为列表以便于后续存为 JSON 字符串
}
```

## 4. 依赖说明

*   **Playwright**: 已在 Phase 1 引入 (`playwright>=1.40.0`)。需要确保运行前执行了 `playwright install chromium`。

## 5. 测试与验收

*   编写 `tests/test_douyin_scraper.py`，测试真实的 Playwright 抓取（因网络原因可能不稳定，可标记为 `@pytest.mark.skipif`，或在本地运行时单独执行）。
*   通过 React 桌面端 UI 输入关键词（例如“Python”），目标视频数量设为 2（MVP演示），点击新建任务，观察终端实时打印真实视频的标题和抓取进度。最终看到成功的 Markdown 报告生成。