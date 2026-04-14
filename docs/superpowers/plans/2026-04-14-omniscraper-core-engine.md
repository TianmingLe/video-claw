# OmniScraper Pro 核心引擎实现计划 (Phase 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭建 Python 后端爬虫引擎的基础设施，包括本地 SQLite 存储模型、防风控中间件接口以及项目依赖配置。

**Architecture:** Python 3.10+ 项目结构，使用 SQLAlchemy 构建 ORM 模型映射视频与评论，使用 pytest 编写单元测试验证数据层逻辑。

**Tech Stack:** Python 3.10, SQLAlchemy, pytest, pytest-asyncio

---

### Task 1: 项目初始化与数据库模型设计

**Files:**
- Create: `requirements.txt`
- Create: `backend/database/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: 创建依赖文件**

```text
# requirements.txt
sqlalchemy>=2.0.0
pytest>=7.0.0
pytest-asyncio>=0.21.0
playwright>=1.40.0
```

- [ ] **Step 2: 编写数据库 ORM 模型代码**

创建 `backend/database/models.py`，定义 `Video`, `Thread`, `Summary` 等核心表结构。

```python
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
    
    video: Mapped["Video"] = relationship(back_populates="summary")

def get_engine(db_path: str = "sqlite:///omniscraper.db"):
    return create_engine(db_path)

def create_tables(engine):
    Base.metadata.create_all(engine)
```

- [ ] **Step 3: 编写失败测试**

创建 `tests/test_models.py`，用于验证模型关系。

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.models import Base, Video, Thread, Summary

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_video_creation(db_session):
    video = Video(
        id="test_v_1", 
        platform="douyin", 
        url="http://test.com/v1", 
        title="Test Video", 
        author="Tester"
    )
    db_session.add(video)
    db_session.commit()
    
    saved_video = db_session.query(Video).filter_by(id="test_v_1").first()
    assert saved_video is not None
    assert saved_video.platform == "douyin"

def test_video_thread_relationship(db_session):
    video = Video(id="test_v_2", platform="xhs", url="url", title="Title", author="Author")
    thread = Thread(root_comment="Great video!", is_valuable=True)
    video.threads.append(thread)
    
    db_session.add(video)
    db_session.commit()
    
    saved_video = db_session.query(Video).filter_by(id="test_v_2").first()
    assert len(saved_video.threads) == 1
    assert saved_video.threads[0].is_valuable is True
```

- [ ] **Step 4: 运行测试并安装依赖**

执行命令安装依赖并运行测试：
```bash
pip install -r requirements.txt
pytest tests/test_models.py -v
```
Expected: PASS

- [ ] **Step 5: 提交代码**

```bash
git init
git add requirements.txt backend/ tests/
git commit -m "feat: setup project structure and database ORM models"
```

---

### Task 2: 基础防风控中间件设计 (AntiBot)

**Files:**
- Create: `backend/middleware/anti_bot.py`
- Create: `tests/test_anti_bot.py`

- [ ] **Step 1: 编写防风控中间件测试**

创建 `tests/test_anti_bot.py`
```python
import pytest
import time
import asyncio
from backend.middleware.anti_bot import AntiBotController

@pytest.mark.asyncio
async def test_random_delay_normal_mode():
    controller = AntiBotController(mode="normal")
    start_time = time.time()
    await controller.random_delay("search")
    duration = time.time() - start_time
    assert 0.3 <= duration <= 1.5 # normal 模式 search 延迟通常在 0.3 到 1.2 秒左右，给一点误差余量

@pytest.mark.asyncio
async def test_random_delay_special_forces_mode():
    controller = AntiBotController(mode="special_forces")
    start_time = time.time()
    await controller.random_delay("search")
    duration = time.time() - start_time
    assert 0.1 <= duration <= 0.6 # special_forces 模式更短
```

- [ ] **Step 2: 编写中间件实现代码**

创建 `backend/middleware/anti_bot.py`
```python
import random
import asyncio

class AntiBotController:
    def __init__(self, mode: str = "normal"):
        """
        mode: "normal" (省心模式) 或 "special_forces" (特种战士模式)
        """
        self.mode = mode
        
        # 基础延迟配置 (单位: 秒) [min, max]
        self.delay_config = {
            "normal": {
                "search": [0.3, 1.2],
                "click_video": [0.8, 2.0],
                "scroll_comments": [1.0, 2.5]
            },
            "special_forces": {
                "search": [0.1, 0.5],
                "click_video": [0.3, 1.0],
                "scroll_comments": [0.5, 1.2]
            }
        }
        
    async def random_delay(self, action: str):
        """执行拟人化随机延迟"""
        config = self.delay_config.get(self.mode, self.delay_config["normal"])
        action_delay = config.get(action, [1.0, 2.0]) # 默认 1-2 秒
        
        # 随机取值
        delay_time = random.uniform(action_delay[0], action_delay[1])
        await asyncio.sleep(delay_time)

    def check_safety_limit(self, current_depth: int, max_depth: int) -> bool:
        """检查是否触及安全底线（防止即使是特种战士模式也把账号拉爆）"""
        # 底层硬编码安全上限（例如：单次抓取绝对不允许超过 5000 条评论）
        HARD_LIMIT = 5000
        actual_max = min(max_depth, HARD_LIMIT)
        return current_depth < actual_max
```

- [ ] **Step 3: 运行中间件测试**

```bash
pytest tests/test_anti_bot.py -v
```
Expected: PASS

- [ ] **Step 4: 提交代码**

```bash
git add backend/middleware/anti_bot.py tests/test_anti_bot.py
git commit -m "feat: implement anti-bot middleware with normal and special forces modes"
```
