import json

from sqlalchemy.orm import sessionmaker

from backend.admin.data_management import clear_reports_content
from backend.database.models import Summary, create_tables, get_engine


def test_clear_reports_content(tmp_path):
    db_file = tmp_path / "c.db"
    engine = get_engine(f"sqlite:///{db_file}")
    create_tables(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        s = Summary(video_id="v1")
        s.report_markdown = "x"
        s.key_points_json = json.dumps(["a"])
        s.actionable_insights = "y"
        s.model_name = "m"
        db.add(s)
        db.commit()

        cleared = clear_reports_content(db)
        db.refresh(s)
        assert cleared == 1
        assert s.report_markdown is None
        assert s.key_points_json == "[]"
        assert s.actionable_insights is None
        assert s.model_name == "unknown"

