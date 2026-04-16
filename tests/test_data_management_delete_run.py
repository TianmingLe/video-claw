from sqlalchemy import inspect

from backend.database.models import create_tables, get_engine


def test_tables_exist_after_create_tables(tmp_path):
    db_file = tmp_path / "t.db"
    engine = get_engine(f"sqlite:///{db_file}")
    create_tables(engine)
    insp = inspect(engine)
    names = set(insp.get_table_names())
    assert "task_runs" in names
    assert "task_run_videos" in names
    assert "app_settings" in names

