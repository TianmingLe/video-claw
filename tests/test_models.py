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