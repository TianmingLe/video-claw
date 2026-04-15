# OmniScraper Pro Phase 2: LLM 与多模态接入规格设计 (Spec)

## 1. 目标与范围 (Scope)

基于 Phase 1 已建立的本地 SQLite 模型和防风控基础设施，Phase 2 旨在打通“视频+评论”数据的**多模态解析（ASR/OCR）**与**基于 LLM 的智能筛选及总结**的完整处理流水线。

**核心目标：**
构建一个端到端的分析闭环：输入抓取到的数据 -> 提取多模态文本 -> LLM 判定评论价值 -> LLM 生成总结 -> 落库保存 -> 导出为 Markdown 报告。

**设计原则（方案A）：**
采用**可插拔 Provider (Stub/Fake) 模式**。保证主干流水线（Pipeline）能独立测试和运行，不强依赖真实的、体积庞大的 AI 模型和第三方 SDK，为未来接入真实模型（如 Whisper, PaddleOCR, OpenAI）打好地基。

## 2. 架构与模块划分

系统将拆分为以下独立且松耦合的模块：

### 2.1 多模态解析模块 (`backend/multimodal/`)
*   **`asr.py`**: 音频转文本服务。
    *   定义 `ASRProvider` 接口，包含 `transcribe(video_path: str) -> str` 方法。
    *   实现 `FakeASRProvider` 用于返回模拟转写文本。
*   **`ocr.py`**: 画面文字提取服务。
    *   定义 `OCRProvider` 接口，包含 `extract(video_path: str) -> str` (或返回 JSON 结构) 方法。
    *   实现 `FakeOCRProvider` 用于返回模拟识别结果。

### 2.2 LLM 分析模块 (`backend/llm/`)
*   **`client.py`**: OpenAI 兼容的轻量级 HTTP 客户端（优先使用 `httpx`）。
    *   负责构造请求并解析结构化输出。
    *   实现 `FakeLLMClient` 模拟接口响应。
*   **`analyzer.py`**: 业务分析器。
    *   `analyze_thread(thread: dict) -> dict`: 判定评论树是否有价值，并打标签。
    *   `generate_summary(video_data, asr_text, ocr_text, valuable_threads) -> dict`: 基于所有素材生成干货总结。
*   **`exporter.py`**: 报告生成器。
    *   `export_to_markdown(video_id: str) -> str`: 将入库的数据渲染为标准 Markdown 格式文档。

### 2.3 流水线编排 (`backend/pipeline/`)
*   **`run_analysis.py`**: 核心 Orchestrator。
    *   负责串联上述模块：获取 DB 数据 -> 调 ASR/OCR -> 调 LLM 筛选评论 -> 调 LLM 生成总结 -> 更新 DB -> 导出 Markdown。

## 3. 数据库模型扩展 (`backend/database/models.py`)

在现有基础上增加字段，以存储多模态与 LLM 产物：

*   **`Video` 表扩展**:
    *   增加 `asr_text: Mapped[Optional[str]]` (Text, nullable)
    *   增加 `ocr_text: Mapped[Optional[str]]` (Text, nullable)
*   **`Summary` 表扩展**:
    *   增加 `report_markdown: Mapped[Optional[str]]` (Text, nullable)
    *   增加 `model_name: Mapped[str]` (String(50), 记录生成该总结的模型，如 "gpt-4o-mini")
*   **`Thread` 表保持原样**:
    *   利用现有的 `is_valuable` 和 `value_tags` 字段接收 LLM 输出。

## 4. 依赖策略

*   **新增轻量级依赖**: `httpx` (用于 LLM API 请求) 和 `pydantic` (用于结构化数据校验)。
*   **隔离重度依赖**: 真实的 ASR/OCR 库（如 `openai-whisper`, `paddleocr`）不在本阶段引入，仅保留接口。

## 5. 测试策略

*   在 `tests/` 下新增 `test_pipeline_phase2.py`。
*   利用 `FakeASRProvider`, `FakeOCRProvider` 和 `FakeLLMClient`，在基于内存的 SQLite 环境中，编写一个端到端的闭环测试，确保从数据输入到 Markdown 报告输出的链路连贯且无报错。