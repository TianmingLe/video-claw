# OmniScraper Pro Phase 5 Spec

## 目标
将后端的 `FakeLLMClient` 替换为真实的、基于 `openai` 库的大模型调用，从而让系统能够真正利用用户在前端界面传入的 `llm_model`、`llm_api_key` 和 `llm_base_url` 对抓取到的抖音数据（视频标题、点赞量、评论列表等）进行真实的总结与分析。

## 需求详情
1. **依赖升级**：在后端安装官方 `openai` 包（并在 requirements.txt 中补齐）。
2. **客户端替换**：
   - 保留原有的接口协议（即 `LLMClient` 抽象类和 `generate_structured` 方法）。
   - 创建 `RealOpenAIClient`，在其内部实例化 `openai.OpenAI(api_key=..., base_url=...)`。
   - 对请求进行容错封装（异常捕获）。
3. **Pipeline 对接**：
   - 在 `AnalysisPipeline` 初始化时，判断 `config.get("llm_api_key")` 是否有效（如果为空则可以降级回 Fake 或直接报错提示）。
   - 将组装好的真实数据作为 Prompt 传递给 LLM，要求它生成 Pydantic 约束的 JSON（使用 `response_format` 或 System Prompt 强制 JSON）。

## 关键技术点
- 大部分开源模型（例如 DeepSeek / SiliconFlow）支持与 OpenAI 一致的 JSON Mode。如果不完全支持 Structured Outputs (`response_format` JSON Schema)，则退而求其次：在 System Prompt 中强制要求输出纯 JSON 字符串，并通过 `json.loads` 解析。考虑到兼容性，本实现将采用**通用 JSON 提取法**（正则清洗 + `json.loads`）以兼容所有模型。