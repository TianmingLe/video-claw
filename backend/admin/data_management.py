from __future__ import annotations

from sqlalchemy.orm import Session

from backend.database.models import Summary, TaskRun, TaskRunVideo, Thread, Video


def clear_reports_content(db: Session) -> int:
    rows = db.query(Summary).all()
    for r in rows:
        r.report_markdown = None
        r.key_points_json = "[]"
        r.actionable_insights = None
        r.model_name = "unknown"
    db.commit()
    return len(rows)


def delete_run_outputs(db: Session, run_id: int) -> dict[str, int]:
    run_videos_deleted = db.query(TaskRunVideo).filter_by(run_id=run_id).delete(synchronize_session=False)
    threads_deleted = db.query(Thread).filter_by(run_id=run_id).delete(synchronize_session=False)
    summaries_deleted = db.query(Summary).filter_by(run_id=run_id).delete(synchronize_session=False)
    runs_deleted = db.query(TaskRun).filter_by(id=run_id).delete(synchronize_session=False)
    db.commit()
    return {
        "task_run_videos": int(run_videos_deleted),
        "threads": int(threads_deleted),
        "summaries": int(summaries_deleted),
        "task_runs": int(runs_deleted),
    }


def delete_video_global(db: Session, video_id: str) -> dict[str, int]:
    run_videos_deleted = db.query(TaskRunVideo).filter_by(video_id=video_id).delete(synchronize_session=False)
    threads_deleted = db.query(Thread).filter_by(video_id=video_id).delete(synchronize_session=False)
    summaries_deleted = db.query(Summary).filter_by(video_id=video_id).delete(synchronize_session=False)
    videos_deleted = db.query(Video).filter_by(id=video_id).delete(synchronize_session=False)
    db.commit()
    return {
        "task_run_videos": int(run_videos_deleted),
        "threads": int(threads_deleted),
        "summaries": int(summaries_deleted),
        "videos": int(videos_deleted),
    }

