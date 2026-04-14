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
