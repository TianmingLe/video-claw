from sqlalchemy.orm import sessionmaker

from backend.database.models import create_tables, get_engine
from backend.settings.store import SettingsStore


def test_settings_roundtrip(tmp_path):
    db_file = tmp_path / "s.db"
    engine = get_engine(f"sqlite:///{db_file}")
    create_tables(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        store = SettingsStore(db)
        store.set_json(
            "douyin.settings",
            {"cookies": [{"name": "a", "value": "b", "domain": ".douyin.com", "path": "/"}]},
        )
        got = store.get_json("douyin.settings")
        assert got["cookies"][0]["name"] == "a"

