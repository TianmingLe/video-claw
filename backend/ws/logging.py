import json
from datetime import datetime, timezone
from typing import Any, Optional


def build_ws_log(
    *,
    level: str,
    module: str,
    msg: str,
    reason: Optional[str] = None,
    run_id: Optional[int] = None,
    video_id: Optional[str] = None,
    metrics: Optional[dict[str, Any]] = None,
    counts: Optional[dict[str, Any]] = None,
) -> str:
    payload: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "level": level,
        "module": module,
        "msg": msg,
    }
    if reason is not None:
        payload["reason"] = reason
    if run_id is not None:
        payload["run_id"] = run_id
    if video_id is not None:
        payload["video_id"] = video_id
    if metrics is not None:
        payload["metrics"] = metrics
    if counts is not None:
        payload["counts"] = counts
    return json.dumps(payload, ensure_ascii=False)

