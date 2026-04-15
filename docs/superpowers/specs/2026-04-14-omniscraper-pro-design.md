# OmniScraper Pro - 纯本地桌面软件技术规格设计文档 (Spec)

## 1. 产品定位与目标

**OmniScraper Pro** 是一款**纯本地桌面端软件**（支持 Windows/macOS/Linux），旨在为用户提供**多平台短视频及评论的自动化抓取、多模态解析（ASR+OCR）以及基于 LLM 的智能总结**能力。

*   **核心价值**：将海量短视频及评论中的“干货/有效意义对话”提炼成结构化知识库。
*   **部署模式**：纯本地运行，**无中心服务器，无云端账号体系**。数据完全保留在用户本地硬盘。
*   **跨端查看妥协方案**：通过导出 Excel、CSV、JSON、Markdown 及 Word 文档，供用户发送至移动端或其他设备查看。

## 2. 核心架构设计

软件将采用 **Electron + React + Python (FastAPI/Playwright)** 的混合架构。

*   **前端 (Electron + React)**：负责提供美观的用户界面（配置任务、查看进度、阅读报告、导出数据）。
*   **后端 (Python 进程)**：由 Electron 启动的本地 Python 服务（打包为独立环境）。负责核心的爬虫调度、浏览器自动化 (Playwright)、多模态处理 (ASR/OCR) 和 LLM 交互。
*   **本地存储**：使用 SQLite 数据库存储所有任务、视频元数据、评论线程和生成的知识点。

## 3. 功能模块详细设计

### 3.1 任务配置与调度引擎

*   **多平台支持**：第一版重点实现**抖音、小红书、Bilibili**（达到可用级别），代码结构预留 YouTube、快手接口。
*   **灵活采集参数**：
    *   **目标平台**：支持单选或多选（可同时下发多个平台的并发抓取任务）。
    *   **关键词输入**：支持多行批量输入（同一个任务内多个关键词视为 1 次执行）。
    *   **深度自定义**：视频数量 (Top N)、一级评论深度 (Top M)、每条回复深度 (Top K)。
*   **智能风控与拟人化中间件**：
    *   **随机延迟**：在点击、滚动、翻页间加入随机等待（例如：搜索输入 300-1200ms，点击视频 800-2000ms）。
    *   **拟人动作（可选）**：用户可勾选是否偶尔点赞/收藏（需设置每日上限，默认关闭）。
    *   **验证码拦截与接管**：
        *   遇到验证码（如滑块），优先尝试内置的简单滑动轨迹策略。
        *   如果多次失败或遇到强制登录墙：暂停爬虫进程，通过 WebSocket 通知 Electron 前端。前端弹窗提示用户：“遇到验证码或登录要求，请接管浏览器”。
        *   用户在弹出的可见浏览器窗口中手动完成验证/登录后，点击“继续任务”。
*   **任务安全档位**：
    *   **省心模式（普通配置）**：限制采集深度，增加请求间隔，降低风控概率。
    *   **特种战士模式（无限配置）**：允许较高的采集深度和较短的请求间隔，但底层仍会强制保留基础的安全防风控底线（适合已经有成熟代理或抗风控经验的用户）。*（注：因取消了云端账号体系，此模式将在本地直接开放，或作为“高级设置”隐藏，由用户自行承担封号风险）*。

### 3.2 多模态内容解析流水线

视频下载至本地临时目录（如 `~/.omniscraper/temp/`）后，进入解析流水线，**解析完成后立即删除 `.mp4` 文件**释放空间。

*   **音频转文本 (ASR)**：提取视频音轨，调用 ASR 引擎（默认使用本地轻量级 Whisper 模型，或支持用户配置如阿里/百度的 API）转写为文本。
*   **画面文字识别 (OCR)**：每秒/关键帧抽取画面，使用本地 OCR（如 PaddleOCR/Tesseract）提取字幕或 PPT 文字。
*   **多模态大模型 (VLM) 预留**：代码中预留 `analyze_video_with_vlm(video_path)` 接口，未来用户填入 GPT-4V/Qwen-VL 等 API Key 时可直接让模型“看懂”视频内容。

### 3.3 LLM 智能分析与知识库

*   **模型接入**：支持配置兼容 OpenAI 格式的 API（Base URL + API Key），预留 OpenClaw 接口。
*   **有效评论筛选与结构化**：
    *   将抓取到的所有评论树（一级+回复）送入 LLM。
    *   LLM 判定是否为“有干货/有意义”的对话。
    *   提取完整线程，并自动打上领域标签（如：#运营技巧）。
*   **Markdown 报告生成**：包含视频链接、高赞评论、有意义对话记录（附原链接）、详细知识点总结。
*   **本地知识库视图**：
    *   汇总所有历史任务提取的知识点和对话。
    *   支持全文搜索、按平台/标签过滤。

### 3.4 数据管理与导出

*   **本地 SQLite 存储**：结构化存储视频、评论线程（`threads` 表包含 `root_comment`, `replies`, `is_valuable`, `value_tags`）、总结（`summary` 表包含 `key_points`, `actionable_insights`）。
*   **多格式导出**：一键导出 Excel、CSV、JSON、Markdown 以及 **Word** 文档（满足多端查看需求）。
*   **兼容旧版知识点文档**：保留原有的知识点文档格式并支持单独下载。

## 4. 技术栈选型

*   **前端/外壳**：Electron (桌面打包), React (UI), Tailwind CSS (样式), Lucide React (图标)。
*   **后端/爬虫核心**：Python 3.10+。
*   **自动化测试/爬虫**：Playwright (支持 Chromium/Firefox/WebKit，抗指纹能力强)。
*   **本地数据库**：SQLite 3 (配合 SQLAlchemy ORM 或直接 SQL)。
*   **多模态库 (预留/本地化)**：`faster-whisper` (ASR), `paddleocr` (OCR), `moviepy`/`ffmpeg-python` (音视频处理)。
*   **LLM 调用**：`openai` python 官方库（或 `httpx` 直接请求），配合 `pydantic` 定义结构化输出。
*   **进程通信**：Electron 与 Python 进程间通过 WebSocket 或本地 HTTP API (FastAPI) 进行实时通信（传递进度、日志、验证码接管事件）。

## 5. 项目文件结构规划 (概念)

```text
omni-scraper-pro/
├── app/                  # Electron 桌面端主进程代码
│   ├── main.js           # 启动窗口、管理 Python 子进程
│   └── preload.js        # IPC 通信预加载
├── src/                  # React 前端渲染进程代码
│   ├── components/       # UI 组件 (面板、配置卡片、进度条)
│   ├── pages/            # 路由页面 (任务、知识库、设置)
│   └── App.tsx           # 主入口
├── backend/              # Python 爬虫与解析核心 (打包为独立可执行环境)
│   ├── main.py           # FastAPI/WebSocket 服务入口
│   ├── scrapers/         # 多平台爬虫适配层 (工厂模式)
│   │   ├── base.py       # BaseScraper 接口
│   │   ├── douyin.py     # 抖音实现
│   │   ├── xiaohongshu.py# 小红书实现
│   │   └── bilibili.py   # B站实现
│   ├── middleware/       # 中间件
│   │   └── anti_bot.py   # 智能限速、拟人动作、验证码拦截器
│   ├── multimodal/       # 多模态解析流水线
│   │   ├── asr.py        # 音频转文本
│   │   ├── ocr.py        # 画面文字识别
│   │   └── vlm_stub.py   # 多模态大模型预留接口
│   ├── llm/              # LLM 分析与总结模块
│   │   ├── analyzer.py   # 评论打分、知识点提取 prompt 构建
│   │   └── exporter.py   # 生成 Markdown/Word 报告
│   └── database/         # SQLite 模型与操作
│       ├── models.py     # 视频、评论、知识点表结构
│       └── db_utils.py
└── package.json          # Electron/React 依赖
```

## 6. 后续开发计划建议

由于这是一个复杂的全栈项目（包含复杂的逆向工程/反反爬），建议分阶段实施：

1.  **阶段一（核心链路打通）**：先跑通“Python 后端 + Playwright 抖音无头抓取 + SQLite 存储”的命令行版本。暂不加复杂的多模态和 LLM，确保能稳定拿到数据和突破基本风控。
2.  **阶段二（LLM与多模态接入）**：接入 OpenAI 接口进行评论筛选和知识点总结，跑通完整的 Markdown 报告生成。加入基础的 ASR/OCR 文本提取。
3.  **阶段三（桌面端与UI）**：开发 Electron + React 界面，与 Python 后端通信，实现用户友好的配置面板和知识库视图。
4.  **阶段四（多平台扩展与优化）**：补充小红书、B站爬虫；完善验证码人工接管流程；添加 Word 导出功能。