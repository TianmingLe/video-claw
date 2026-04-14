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
    assert "[OCR" in saved_v.ocr_text
    
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
