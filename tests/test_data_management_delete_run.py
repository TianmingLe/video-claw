from sqlalchemy import inspect
import json
from sqlalchemy.orm import sessionmaker

from backend.admin.data_management import delete_run_outputs
from backend.database.models import Summary, TaskRun, TaskRunVideo, Thread, Video, create_tables, get_engine


def test_tables_exist_after_create_tables(tmp_path):
    db_file = tmp_path / "t.db"
    engine = get_engine(f"sqlite:///{db_file}")
    create_tables(engine)
    insp = inspect(engine)
    names = set(insp.get_table_names())
    assert "task_runs" in names
    assert "task_run_videos" in names
    assert "app_settings" in names


def test_delete_run_outputs_keeps_videos(tmp_path):
    db_file = tmp_path / "d.db"
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

        counts = delete_run_outputs(db, run.id)
        assert counts["task_runs"] == 1
        assert db.query(Video).filter_by(id="v1").first() is not None
        assert db.query(Thread).count() == 0
        assert db.query(Summary).count() == 0
        assert db.query(TaskRunVideo).count() == 0
