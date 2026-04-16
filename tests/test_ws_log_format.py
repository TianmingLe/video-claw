import json

from backend.ws.logging import build_ws_log


def test_ws_log_json_min_fields():
    s = build_ws_log(level="ERROR", module="douyin_scraper", msg="x", reason="DOM_TIMEOUT", run_id=123)
    payload = json.loads(s)
    assert payload["level"] == "ERROR"
    assert payload["module"] == "douyin_scraper"
    assert payload["msg"] == "x"
    assert payload["reason"] == "DOM_TIMEOUT"
    assert payload["run_id"] == 123
    assert "ts" in payload

