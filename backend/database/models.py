import os
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Integer, Boolean, Text, ForeignKey, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy import text

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
    run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("task_runs.id"), nullable=True)
    
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
    run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("task_runs.id"), nullable=True)
    
    video: Mapped["Video"] = relationship(back_populates="summary")


class TaskRun(Base):
    __tablename__ = "task_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(nullable=True)
    platform: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    keyword: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    depth: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(20), default="running")
    error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    metrics_json: Mapped[str] = mapped_column(Text, default="{}")


class TaskRunVideo(Base):
    __tablename__ = "task_run_videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("task_runs.id"))
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id"))


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

def get_engine(db_path: str = "sqlite:///omniscraper.db"):
    engine = create_engine(
        db_path,
        connect_args={"check_same_thread": False} if db_path.startswith("sqlite") else {},
    )
    if db_path.startswith("sqlite"):
        with engine.connect() as conn:
            try:
                conn.execute(text("PRAGMA journal_mode=WAL"))
            except Exception:
                pass
    return engine

def create_tables(engine):
    Base.metadata.create_all(engine)
    if engine.dialect.name != "sqlite":
        return

    with engine.connect() as conn:
        def has_column(table: str, column: str) -> bool:
            rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            return any(r[1] == column for r in rows)

        if not has_column("threads", "run_id"):
            conn.execute(text("ALTER TABLE threads ADD COLUMN run_id INTEGER"))

        if not has_column("summaries", "run_id"):
            conn.execute(text("ALTER TABLE summaries ADD COLUMN run_id INTEGER"))

        conn.commit()
