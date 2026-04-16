import json
from typing import Any

from sqlalchemy.orm import Session

from backend.database.models import AppSetting


class SettingsStore:
    def __init__(self, db: Session):
        self.db = db

    def get(self, key: str) -> str | None:
        row = self.db.get(AppSetting, key)
        return row.value if row else None

    def set(self, key: str, value: str) -> None:
        row = self.db.get(AppSetting, key)
        if row:
            row.value = value
        else:
            self.db.add(AppSetting(key=key, value=value))
        self.db.commit()

    def get_json(self, key: str) -> dict[str, Any]:
        raw = self.get(key)
        if not raw:
            return {}
        try:
            val = json.loads(raw)
            if isinstance(val, dict):
                return val
        except Exception:
            return {}
        return {}

    def set_json(self, key: str, value: dict[str, Any]) -> None:
        self.set(key, json.dumps(value, ensure_ascii=False))

