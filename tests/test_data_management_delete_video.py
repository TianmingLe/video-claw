import json

from sqlalchemy.orm import sessionmaker

from backend.admin.data_management import delete_video_global
from backend.database.models import Summary, TaskRun, TaskRunVideo, Thread, Video, create_tables, get_engine


def test_delete_video_global(tmp_path):
    db_file = tmp_path / "v.db"
    engine = get_engine(f"sqlite:///{db_file}")
    create_tables(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        run = TaskRun(platform="douyin", keyword="k", depth=1, status="success")
        db.add(run)
        db.commit()

        v = Video(id="v1", platform="douyin", url="u", title="t", author="a", like_count=0)
        db.add(v)
        db.commit()

        db.add(TaskRunVideo(run_id=run.id, video_id=v.id))
        db.add(Thread(video_id=v.id, root_comment="c", replies_json=json.dumps([]), run_id=run.id))
        db.add(Summary(video_id=v.id, report_markdown="md", model_name="m", run_id=run.id))
        db.commit()

        counts = delete_video_global(db, "v1")
        assert counts["videos"] == 1
        assert db.query(Video).filter_by(id="v1").first() is None
        assert db.query(Thread).count() == 0
        assert db.query(Summary).count() == 0
        assert db.query(TaskRunVideo).count() == 0

