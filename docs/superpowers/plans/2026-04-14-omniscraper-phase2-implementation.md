# OmniScraper Pro Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于 Provider/Client 模式实现多模态提取 (ASR/OCR) 与 LLM 评论价值判定及总结的完整端到端闭环。

**Architecture:** 扩展现有的 SQLAlchemy 模型以支持多模态和 Markdown 结果的存储。实现接口层及其 Fake 实现，最后通过 Pipeline Orchestrator (`run_analysis.py`) 将获取数据、ASR/OCR 提取、LLM 判定及报告生成串联起来，形成完整的流程闭环。

**Tech Stack:** Python 3.10, SQLAlchemy, pytest, pytest-asyncio, pydantic

---

### Task 1: 扩展数据库模型与依赖配置

**Files:**
- Modify: `requirements.txt`
- Modify: `backend/database/models.py`
- Modify: `tests/test_models.py`

- [ ] **Step 1: 增加 `pydantic` 依赖**

修改 `requirements.txt`：
```text
sqlalchemy>=2.0.0
pytest>=7.0.0
pytest-asyncio>=0.21.0
playwright>=1.40.0
pydantic>=2.0.0
```

- [ ] **Step 2: 扩展 SQLAlchemy 模型字段**

修改 `backend/database/models.py`，为 `Video` 和 `Summary` 增加新字段：
```python
# ... 现有的 imports 保持不变 ...
import os
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Integer, Boolean, Text, ForeignKey, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

class Base(DeclarativeBase):
    pass

class Video(Base):
    __tablename__ = "videos"
    
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    platform: Mapped[str] = mapped_column(String(20)) # douyin, xhs, bilibili
    url: Mapped[str] = mapped_column(String(500))
    title: Mapped[str] = mapped_column(String(255))
    author: Mapped[str] = mapped_column(String(100))
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    
    # Phase 2: 多模态字段
    asr_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ocr_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    threads: Mapped[List["Thread"]] = relationship(back_populates="video", cascade="all, delete-orphan")
    summary: Mapped["Summary"] = relationship(back_populates="video", cascade="all, delete-orphan", uselist=False)

class Thread(Base):
    __tablename__ = "threads"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id"))
    root_comment: Mapped[str] = mapped_column(Text)
    replies_json: Mapped[str] = mapped_column(Text, default="[]") # 存储嵌套回复JSON
    is_valuable: Mapped[bool] = mapped_column(Boolean, default=False)
    value_tags: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    
    video: Mapped["Video"] = relationship(back_populates="threads")

class Summary(Base):
    __tablename__ = "summaries"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id"))
    key_points_json: Mapped[str] = mapped_column(Text, default="[]")
    actionable_insights: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Phase 2: 报告与模型记录
    report_markdown: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_name: Mapped[str] = mapped_column(String(50), default="unknown")
    
    video: Mapped["Video"] = relationship(back_populates="summary")

def get_engine(db_path: str = "sqlite:///omniscraper.db"):
    return create_engine(db_path)

def create_tables(engine):
    Base.metadata.create_all(engine)
```

- [ ] **Step 3: 更新测试用例验证新字段**

在 `tests/test_models.py` 中添加 `test_phase2_fields`：
```python
# ... 在文件末尾追加 ...

def test_phase2_fields(db_session):
    video = Video(id="test_v_3", platform="bilibili", url="url", title="T", author="A", asr_text="Hello", ocr_text="World")
    summary = Summary(report_markdown="# Report", model_name="fake-model")
    video.summary = summary
    db_session.add(video)
    db_session.commit()
    
    saved_video = db_session.query(Video).filter_by(id="test_v_3").first()
    assert saved_video.asr_text == "Hello"
    assert saved_video.ocr_text == "World"
    assert saved_video.summary.report_markdown == "# Report"
    assert saved_video.summary.model_name == "fake-model"
```

- [ ] **Step 4: 安装新依赖并运行测试**

```bash
pip install -r requirements.txt
PYTHONPATH=. pytest tests/test_models.py -v
```
Expected: PASS

- [ ] **Step 5: 提交代码**

```bash
git add requirements.txt backend/database/models.py tests/test_models.py
git commit -m "feat: extend db models with phase 2 multimodal and report fields"
```

---

### Task 2: 实现多模态解析 Provider

**Files:**
- Create: `backend/multimodal/asr.py`
- Create: `backend/multimodal/ocr.py`

- [ ] **Step 1: 实现 ASR Provider**

创建 `backend/multimodal/asr.py`：
```python
from abc import ABC, abstractmethod

class ASRProvider(ABC):
    @abstractmethod
    def transcribe(self, video_path: str) -> str:
        pass

class FakeASRProvider(ASRProvider):
    def transcribe(self, video_path: str) -> str:
        return f"[ASR] Simulated transcription for {video_path}: This video talks about great tips."
```

- [ ] **Step 2: 实现 OCR Provider**

创建 `backend/multimodal/ocr.py`：
```python
from abc import ABC, abstractmethod

class OCRProvider(ABC):
    @abstractmethod
    def extract(self, video_path: str) -> str:
        pass

class FakeOCRProvider(OCRProvider):
    def extract(self, video_path: str) -> str:
        return f"[OCR] Simulated text extracted from {video_path}: Tip 1, Tip 2, Conclusion."
```

- [ ] **Step 3: 提交代码**

```bash
git add backend/multimodal/
git commit -m "feat: add multimodal asr and ocr provider interfaces and fake implementations"
```

---

### Task 3: 实现 LLM Client 与 Analyzer

**Files:**
- Create: `backend/llm/client.py`
- Create: `backend/llm/analyzer.py`

- [ ] **Step 1: 实现 LLM Fake Client**

创建 `backend/llm/client.py`，使用 pydantic 作为 schema 约束基础：
```python
import json
from abc import ABC, abstractmethod
from typing import Type, TypeVar, Any
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)

class LLMClient(ABC):
    @abstractmethod
    def generate_structured(self, prompt: str, schema: Type[T]) -> T:
        pass

class FakeLLMClient(LLMClient):
    def __init__(self, model_name: str = "fake-gpt-4o-mini"):
        self.model_name = model_name
        
    def generate_structured(self, prompt: str, schema: Type[T]) -> T:
        """根据 schema 类名返回硬编码的模拟数据"""
        schema_name = schema.__name__
        
        if schema_name == "ThreadAnalysis":
            return schema(**{
                "is_valuable": True,
                "value_tags": "tips, tutorial",
                "reason": "Simulated value detection."
            })
            
        elif schema_name == "VideoSummary":
            return schema(**{
                "key_points": ["Point 1", "Point 2"],
                "actionable_insights": "Do this simulated action."
            })
            
        # Fallback
        raise ValueError(f"Unknown schema: {schema_name}")
```

- [ ] **Step 2: 实现业务分析器 (Analyzer)**

创建 `backend/llm/analyzer.py`：
```python
from pydantic import BaseModel
from typing import List, Dict, Any
from backend.llm.client import LLMClient

class ThreadAnalysis(BaseModel):
    is_valuable: bool
    value_tags: str
    reason: str

class VideoSummary(BaseModel):
    key_points: List[str]
    actionable_insights: str

class LLMAnalyzer:
    def __init__(self, client: LLMClient):
        self.client = client
        
    def analyze_thread(self, root_comment: str, replies: str) -> ThreadAnalysis:
        prompt = f"Analyze this thread: {root_comment} | Replies: {replies}"
        return self.client.generate_structured(prompt, ThreadAnalysis)
        
    def generate_summary(self, video_title: str, asr_text: str, ocr_text: str, valuable_threads: List[Dict[str, Any]]) -> VideoSummary:
        prompt = f"Summarize video '{video_title}'. ASR: {asr_text}. OCR: {ocr_text}. Threads: {len(valuable_threads)}"
        return self.client.generate_structured(prompt, VideoSummary)
```

- [ ] **Step 3: 提交代码**

```bash
git add backend/llm/client.py backend/llm/analyzer.py
git commit -m "feat: implement llm fake client and analyzer for thread and video summarization"
```

---

### Task 4: 实现 Markdown 报告生成器

**Files:**
- Create: `backend/llm/exporter.py`

- [ ] **Step 1: 实现 Exporter 逻辑**

创建 `backend/llm/exporter.py`：
```python
import json

class MarkdownExporter:
    @staticmethod
    def generate_report(video, threads, summary) -> str:
        """
        根据 ORM 对象或字典构建 Markdown 报告。
        """
        title = video.title if hasattr(video, 'title') else video.get('title', 'Unknown Video')
        url = video.url if hasattr(video, 'url') else video.get('url', '#')
        
        md_lines = []
        md_lines.append(f"# Video Analysis Report: {title}")
        md_lines.append(f"**URL:** {url}")
        md_lines.append("\n## 1. Key Points")
        
        # 尝试解析 summary 的 key_points_json
        key_points = []
        kp_json = summary.key_points_json if hasattr(summary, 'key_points_json') else summary.get('key_points_json', '[]')
        try:
            key_points = json.loads(kp_json)
        except:
            key_points = [kp_json]
            
        for pt in key_points:
            md_lines.append(f"- {pt}")
            
        md_lines.append("\n## 2. Actionable Insights")
        insights = summary.actionable_insights if hasattr(summary, 'actionable_insights') else summary.get('actionable_insights', '')
        md_lines.append(insights or "None")
        
        md_lines.append("\n## 3. Valuable Conversations")
        valuable_threads = [t for t in threads if (getattr(t, 'is_valuable', False) or t.get('is_valuable') is True)]
        
        if not valuable_threads:
            md_lines.append("No valuable conversations found.")
        else:
            for i, t in enumerate(valuable_threads):
                tags = getattr(t, 'value_tags', '') or t.get('value_tags', '')
                root = getattr(t, 'root_comment', '') or t.get('root_comment', '')
                md_lines.append(f"### Thread {i+1} [Tags: {tags}]")
                md_lines.append(f"> {root}")
                md_lines.append("")
                
        return "\n".join(md_lines)
```

- [ ] **Step 2: 提交代码**

```bash
git add backend/llm/exporter.py
git commit -m "feat: implement markdown report exporter"
```

---

### Task 5: Pipeline 编排与闭环测试

**Files:**
- Create: `backend/pipeline/run_analysis.py`
- Create: `tests/test_pipeline_phase2.py`

- [ ] **Step 1: 实现 Pipeline Orchestrator**

创建 `backend/pipeline/run_analysis.py`：
```python
import json
from sqlalchemy.orm import Session
from backend.database.models import Video, Thread, Summary
from backend.multimodal.asr import FakeASRProvider
from backend.multimodal.ocr import FakeOCRProvider
from backend.llm.client import FakeLLMClient
from backend.llm.analyzer import LLMAnalyzer
from backend.llm.exporter import MarkdownExporter

class AnalysisPipeline:
    def __init__(self, db_session: Session):
        self.db = db_session
        self.asr_provider = FakeASRProvider()
        self.ocr_provider = FakeOCRProvider()
        self.llm_client = FakeLLMClient()
        self.analyzer = LLMAnalyzer(self.llm_client)
        self.exporter = MarkdownExporter()

    def run_for_video(self, video_id: str, local_video_path: str = "dummy.mp4"):
        # 1. 查询视频
        video = self.db.query(Video).filter_by(id=video_id).first()
        if not video:
            raise ValueError(f"Video {video_id} not found in DB")

        # 2. 多模态提取
        video.asr_text = self.asr_provider.transcribe(local_video_path)
        video.ocr_text = self.ocr_provider.extract(local_video_path)
        self.db.commit()

        # 3. 分析线程价值
        threads = self.db.query(Thread).filter_by(video_id=video_id).all()
        valuable_threads_data = []
        for t in threads:
            analysis = self.analyzer.analyze_thread(t.root_comment, t.replies_json)
            t.is_valuable = analysis.is_valuable
            t.value_tags = analysis.value_tags
            
            if t.is_valuable:
                valuable_threads_data.append({
                    "root": t.root_comment,
                    "tags": t.value_tags
                })
        self.db.commit()

        # 4. 生成总结
        summary_obj = self.analyzer.generate_summary(
            video_title=video.title,
            asr_text=video.asr_text,
            ocr_text=video.ocr_text,
            valuable_threads=valuable_threads_data
        )
        
        db_summary = self.db.query(Summary).filter_by(video_id=video_id).first()
        if not db_summary:
            db_summary = Summary(video_id=video_id)
            self.db.add(db_summary)
            
        db_summary.key_points_json = json.dumps(summary_obj.key_points)
        db_summary.actionable_insights = summary_obj.actionable_insights
        db_summary.model_name = self.llm_client.model_name
        self.db.commit()

        # 5. 生成并保存 Markdown 报告
        report_md = self.exporter.generate_report(video, threads, db_summary)
        db_summary.report_markdown = report_md
        self.db.commit()
        
        return report_md
```

- [ ] **Step 2: 编写端到端闭环测试**

创建 `tests/test_pipeline_phase2.py`：
```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.models import Base, Video, Thread
from backend.pipeline.run_analysis import AnalysisPipeline

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_full_pipeline(db_session):
    # 准备假数据
    v = Video(id="v_pipe_1", platform="douyin", url="http://x", title="Amazing Pipeline", author="Test")
    t1 = Thread(video_id="v_pipe_1", root_comment="Great video!", replies_json="[]")
    t2 = Thread(video_id="v_pipe_1", root_comment="Nice!", replies_json="[]")
    
    db_session.add(v)
    db_session.add(t1)
    db_session.add(t2)
    db_session.commit()

    # 运行流水线
    pipeline = AnalysisPipeline(db_session)
    report = pipeline.run_for_video("v_pipe_1", "dummy.mp4")

    # 验证数据库更新
    saved_v = db_session.query(Video).filter_by(id="v_pipe_1").first()
    assert "[ASR]" in saved_v.asr_text
    assert "[OCR]" in saved_v.ocr_text
    
    # 验证 Thread 分析结果（Fake 返回 True）
    assert len(saved_v.threads) == 2
    assert saved_v.threads[0].is_valuable is True
    assert saved_v.threads[0].value_tags == "tips, tutorial"
    
    # 验证 Summary 和 Report
    assert saved_v.summary is not None
    assert saved_v.summary.model_name == "fake-gpt-4o-mini"
    assert saved_v.summary.report_markdown is not None
    assert "Amazing Pipeline" in saved_v.summary.report_markdown
    assert "tips, tutorial" in saved_v.summary.report_markdown
```

- [ ] **Step 3: 运行全量测试**

```bash
PYTHONPATH=. pytest tests/ -v
```
Expected: PASS

- [ ] **Step 4: 提交代码**

```bash
git add backend/pipeline/ tests/test_pipeline_phase2.py
git commit -m "feat: implement orchestrator pipeline and end-to-end test for phase 2"
```
