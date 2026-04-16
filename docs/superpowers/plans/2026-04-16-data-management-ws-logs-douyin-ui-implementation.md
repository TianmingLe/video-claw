# Data Management + WS Structured Logs + Douyin UI Scrape Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add production-grade data management (clear/delete by run/video), structured WS logs (JSON-first), global Douyin cookies, and Douyin UI-driven search scraping (no mock fallback).

**Architecture:** Introduce `TaskRun` + `TaskRunVideo` to track per-run outputs. Add admin APIs for clearing reports, deleting run outputs, deleting per-video data, and async/batched “delete all runs”. Emit JSON WS logs through a centralized logger helper. Rework Douyin scraper to start at `https://www.douyin.com/` and perform in-page search interactions; remove mock data generation and surface explicit error codes.

**Tech Stack:** FastAPI + SQLAlchemy (SQLite), Playwright, React (Vite), WebSocket.

---

## File Map (What to touch)

**Backend**
- Modify: `backend/database/models.py` (add tables/columns: task_runs, task_run_videos, app_settings, run_id fields)
- Modify: `backend/main.py` (WS logger helper, task run lifecycle, new APIs, async delete job registry)
- Modify: `backend/scrapers/douyin.py` (UI-driven search flow, retries, login wall detection, cookie + UA injection hooks)
- Modify: `backend/middleware/anti_bot.py` (add jitter delay + retry helper if needed)
- Add: `backend/ws/logging.py` (structured log schema + `ws_log` helper)
- Add: `backend/admin/data_management.py` (DB ops for clear/delete, batched deletes, VACUUM helpers)
- Add: `backend/settings/store.py` (read/write `app_settings` with safe redaction)

**Frontend**
- Modify: `visual-companion/src/App.tsx` (WS JSON parsing + UI Data Management modal + cookie editor + delete buttons)

**Tests**
- Add: `tests/test_data_management_clear_reports.py`
- Add: `tests/test_data_management_delete_run.py`
- Add: `tests/test_data_management_delete_video.py`
- Add: `tests/test_ws_log_format.py`

---

## Task 1: Add DB schema for TaskRun / TaskRunVideo / AppSettings

**Files:**
- Modify: `backend/database/models.py`
- Test: `tests/test_data_management_delete_run.py` (initial failing scaffolding)

- [ ] **Step 1: Add failing test for schema presence**

Create `tests/test_data_management_delete_run.py`:

```python
from sqlalchemy import inspect
from backend.database.models import get_engine, create_tables

def test_tables_exist_after_create_tables(tmp_path):
    db_file = tmp_path / "t.db"
    engine = get_engine(f"sqlite:///{db_file}")
    create_tables(engine)
    insp = inspect(engine)
    names = set(insp.get_table_names())
    assert "task_runs" in names
    assert "task_run_videos" in names
    assert "app_settings" in names
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_data_management_delete_run.py::test_tables_exist_after_create_tables -q`
Expected: FAIL (tables missing)

- [ ] **Step 3: Implement schema changes**

Update `backend/database/models.py` to add:

- `TaskRun` model:
  - `id` int PK autoincrement
  - `created_at` datetime default utcnow
  - `started_at` nullable datetime
  - `finished_at` nullable datetime
  - `duration_ms` nullable int
  - `platform`, `keyword`, `depth`
  - `config_json` Text default `"{}"`
  - `status` String default `"running"`
  - `error_code` nullable String
  - `metrics_json` Text default `"{}"`
- `TaskRunVideo` model:
  - `id` int PK autoincrement
  - `run_id` FK `task_runs.id`
  - `video_id` FK `videos.id`
- `AppSetting` model:
  - `key` String PK
  - `value` Text
  - `updated_at` datetime default utcnow
- Add columns:
  - `Thread.run_id` nullable int FK `task_runs.id`
  - `Summary.run_id` nullable int FK `task_runs.id`

Notes for SQLite compatibility:
- Since this project uses `create_all` (no migrations), adding columns to existing tables may require manual ALTER in runtime. Implement a minimal “ensure schema” step in `create_tables(engine)`:
  - Check missing columns via `PRAGMA table_info` and execute `ALTER TABLE ... ADD COLUMN ...` for new nullable columns.
  - Create new tables via `Base.metadata.create_all`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_data_management_delete_run.py::test_tables_exist_after_create_tables -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/database/models.py tests/test_data_management_delete_run.py
git commit -m "feat(db): add task run and app settings schema"
```

---

## Task 2: Implement structured WS logger (JSON-first) with compatibility

**Files:**
- Add: `backend/ws/logging.py`
- Modify: `backend/main.py`
- Test: `tests/test_ws_log_format.py`

- [ ] **Step 1: Add failing test for WS log JSON shape**

Create `tests/test_ws_log_format.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ws_log_format.py::test_ws_log_json_min_fields -q`
Expected: FAIL (module missing)

- [ ] **Step 3: Implement logger helper**

Create `backend/ws/logging.py`:

```python
import json
from datetime import datetime, timezone
from typing import Any, Optional

def build_ws_log(*, level: str, module: str, msg: str, reason: Optional[str] = None, run_id: Optional[int] = None, video_id: Optional[str] = None, metrics: Optional[dict[str, Any]] = None, counts: Optional[dict[str, Any]] = None) -> str:
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
```

Update `backend/main.py`:
- Add helper `async def ws_log(...): await manager.broadcast(build_ws_log(...))`
- Keep compatibility for existing string logs where not yet migrated.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ws_log_format.py::test_ws_log_json_min_fields -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/ws/logging.py backend/main.py tests/test_ws_log_format.py
git commit -m "feat(ws): add structured json ws logs"
```

---

## Task 3: Add global Douyin settings store (cookies + UA pool) with redaction

**Files:**
- Add: `backend/settings/store.py`
- Modify: `backend/main.py`
- Modify: `backend/database/models.py` (if needed)

- [ ] **Step 1: Add failing unit test for settings roundtrip**

Create `tests/test_settings_store.py`:

```python
import json
from sqlalchemy.orm import sessionmaker
from backend.database.models import get_engine, create_tables
from backend.settings.store import SettingsStore

def test_settings_roundtrip(tmp_path):
    db_file = tmp_path / "s.db"
    engine = get_engine(f"sqlite:///{db_file}")
    create_tables(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        store = SettingsStore(db)
        store.set_json("douyin.settings", {"cookies": [{"name": "a", "value": "b", "domain": ".douyin.com", "path": "/"}]})
        got = store.get_json("douyin.settings")
        assert got["cookies"][0]["name"] == "a"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_settings_store.py::test_settings_roundtrip -q`
Expected: FAIL

- [ ] **Step 3: Implement SettingsStore**

Create `backend/settings/store.py`:
- `get_json(key) -> dict`
- `set_json(key, value: dict) -> None`
- Always store JSON string; never log raw cookies.

Modify `backend/main.py` to add APIs:
- `GET /api/settings/douyin` returns `{has_cookies: bool, cookies_count: int, user_agent_pool_count: int}`
- `PUT /api/settings/douyin` accepts JSON payload and stores it.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_settings_store.py::test_settings_roundtrip -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/settings/store.py backend/main.py tests/test_settings_store.py
git commit -m "feat(settings): add global douyin settings store and api"
```

---

## Task 4: Implement clear reports content API (keep rows)

**Files:**
- Add: `backend/admin/data_management.py`
- Modify: `backend/main.py`
- Test: `tests/test_data_management_clear_reports.py`

- [ ] **Step 1: Add failing test**

Create `tests/test_data_management_clear_reports.py`:

```python
import json
from sqlalchemy.orm import sessionmaker
from backend.database.models import get_engine, create_tables, Summary
from backend.admin.data_management import clear_reports_content

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_data_management_clear_reports.py::test_clear_reports_content -q`
Expected: FAIL

- [ ] **Step 3: Implement DB helper + API**

Create `backend/admin/data_management.py`:
- `clear_reports_content(db) -> int`

Modify `backend/main.py`:
- `POST /api/admin/reports/clear` calls helper and emits WS log with counts.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_data_management_clear_reports.py::test_clear_reports_content -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/admin/data_management.py backend/main.py tests/test_data_management_clear_reports.py
git commit -m "feat(admin): add clear reports content api"
```

---

## Task 5: Implement delete-by-run API (delete run outputs, keep videos)

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/admin/data_management.py`
- Test: `tests/test_data_management_delete_run.py` (extend)

- [ ] **Step 1: Add failing test for delete-by-run**

Append to `tests/test_data_management_delete_run.py`:

```python
import json
from sqlalchemy.orm import sessionmaker
from backend.database.models import get_engine, create_tables, Video, Thread, Summary, TaskRun, TaskRunVideo
from backend.admin.data_management import delete_run_outputs

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_data_management_delete_run.py::test_delete_run_outputs_keeps_videos -q`
Expected: FAIL

- [ ] **Step 3: Implement delete_run_outputs helper + API**

In `backend/admin/data_management.py`:
- `delete_run_outputs(db, run_id: int) -> dict[str,int]`
- Use transaction; delete in order: task_run_videos, threads, summaries, task_runs.

In `backend/main.py`:
- `DELETE /api/task-runs/{run_id}` returns counts; emits WS logs.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_data_management_delete_run.py::test_delete_run_outputs_keeps_videos -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/admin/data_management.py backend/main.py tests/test_data_management_delete_run.py
git commit -m "feat(admin): add delete run outputs api"
```

---

## Task 6: Implement delete-by-video API (global delete)

**Files:**
- Modify: `backend/admin/data_management.py`
- Modify: `backend/main.py`
- Test: `tests/test_data_management_delete_video.py`

- [ ] **Step 1: Add failing test**

Create `tests/test_data_management_delete_video.py`:

```python
import json
from sqlalchemy.orm import sessionmaker
from backend.database.models import get_engine, create_tables, Video, Thread, Summary, TaskRun, TaskRunVideo
from backend.admin.data_management import delete_video_global

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_data_management_delete_video.py::test_delete_video_global -q`
Expected: FAIL

- [ ] **Step 3: Implement helper + API**

In `backend/admin/data_management.py`:
- `delete_video_global(db, video_id: str) -> dict[str,int]`

In `backend/main.py`:
- `DELETE /api/videos/{video_id}` returns counts; emits WS logs.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_data_management_delete_video.py::test_delete_video_global -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/admin/data_management.py backend/main.py tests/test_data_management_delete_video.py
git commit -m "feat(admin): add delete video global api"
```

---

## Task 7: Implement async “delete all runs” job (batched + WS progress + timeout)

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/admin/data_management.py`

- [ ] **Step 1: Add job registry in backend/main.py**

Implement an in-memory registry:
- `delete_jobs: dict[str, dict]` mapping `task_id -> {status, started_at, counts, error}`
- Use `asyncio.create_task` to run the batched deletion loop.

- [ ] **Step 2: Implement batched deletion function**

In `backend/admin/data_management.py`:
- `delete_all_run_outputs_batched(db_factory, batch_size: int, ws_log_fn, task_id: str) -> dict`
  - Loop: select run_ids in batches, call `delete_run_outputs` per run, commit per run.
  - Emit WS progress with cumulative counts.

- [ ] **Step 3: Wire API**

In `backend/main.py`:
- `DELETE /api/task-runs` returns `{task_id}`
- Optionally `GET /api/admin/tasks/{task_id}`

- [ ] **Step 4: Manual verification**

Run: create a few runs via UI, call delete-all endpoint, confirm WS shows progress and UI refresh shows empty runs.

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/admin/data_management.py
git commit -m "feat(admin): add async batched delete all run outputs"
```

---

## Task 8: Add SQLite pragmas (WAL) and VACUUM endpoint/job

**Files:**
- Modify: `backend/database/models.py` (engine init)
- Modify: `backend/main.py`
- Modify: `backend/admin/data_management.py`

- [ ] **Step 1: Enable WAL for SQLite engine**

In `get_engine(...)`:
- If sqlite, execute `PRAGMA journal_mode=WAL` on connect (SQLAlchemy event listener).

- [ ] **Step 2: Add VACUUM endpoint as async job**

API: `POST /api/admin/db/vacuum` -> `{task_id}`
Job emits WS progress start/finish.

- [ ] **Step 3: Manual verification**

Run: call vacuum endpoint, confirm completes and does not crash server.

- [ ] **Step 4: Commit**

```bash
git add backend/database/models.py backend/main.py backend/admin/data_management.py
git commit -m "chore(db): enable wal and add vacuum admin job"
```

---

## Task 9: Integrate TaskRun lifecycle into task execution

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/pipeline/run_analysis.py` (to accept run_id if needed)

- [ ] **Step 1: Create TaskRun at task start**

In `/api/task/start`:
- Create TaskRun row with status `running`, save config snapshot (redact api keys, never store `llm_api_key`).
- Return `run_id` in response (optional).

- [ ] **Step 2: Attach run_id during DB writes**

When creating Thread/Summary:
- Set `run_id = task_run.id`
When linking video:
- Insert into `task_run_videos`.

- [ ] **Step 3: Record metrics**

At end:
- Set status `success/failed`
- duration_ms, started_at, finished_at
- error_code if failure
- metrics_json with counts

- [ ] **Step 4: Manual verification**

Run a task (depth=1) and ensure:
- `GET /api/task-runs` shows it
- `DELETE /api/task-runs/{id}` removes its outputs but keeps videos

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/pipeline/run_analysis.py
git commit -m "feat(task): record task runs and link outputs"
```

---

## Task 10: Rework Douyin scraper to UI-driven in-page search (no mock)

**Files:**
- Modify: `backend/scrapers/douyin.py`
- Modify: `backend/middleware/anti_bot.py` (optional helpers)

- [ ] **Step 1: Remove mock fallback logic**

In `search_videos`, delete the branch that builds `dy_mock_*` results.

- [ ] **Step 2: Implement UI-driven search**

In `search_videos`:
- `goto("https://www.douyin.com/")`
- wait for a search input (e.g., `input[type="text"]` with heuristics)
- type keyword, press Enter
- wait for results container
- parse video cards (extract href/title)

- [ ] **Step 3: Add retry with exponential backoff**

Wrap navigation/search in retry loop with sleeps 2/4/8 seconds.
Emit WS JSON logs with `reason=RETRYING`.

- [ ] **Step 4: Add login wall detection**

Heuristics:
- detect typical login modal selectors / “登录” text overlays
- or result container absent after timeout
Return `[]` and set error code `LOGIN_REQUIRED` (bubble up to WS in main pipeline).

- [ ] **Step 5: Inject cookies + UA pool**

In `start_browser`:
- load `douyin.settings` from DB (passed into scraper or a provider)
- set `user_agent` from pool
- add cookies to context before navigation

- [ ] **Step 6: Manual verification**

Run with cookies absent:
- Expect ERROR_LOGIN_REQUIRED and no mock URLs stored.

Run with cookies present (manually set via settings endpoint/UI):
- Expect real video URLs.

- [ ] **Step 7: Commit**

```bash
git add backend/scrapers/douyin.py backend/middleware/anti_bot.py
git commit -m "feat(douyin): ui-driven search scrape with retries and no mock"
```

---

## Task 11: Frontend WS JSON parsing + Data Management UI

**Files:**
- Modify: `visual-companion/src/App.tsx`

- [ ] **Step 1: Update WS onmessage to parse JSON**

In `ws.onmessage`:
- Try JSON.parse
- If success, append a formatted line (e.g. `[LEVEL][module] msg`) while also keeping raw JSON for future structured view.
- Use `run_id` if present to group.

- [ ] **Step 2: Add Data Management modal**

UI actions:
- Clear reports: `POST /api/admin/reports/clear`
- List runs: `GET /api/task-runs?limit=20`
- Delete run: `DELETE /api/task-runs/{run_id}`
- Delete all runs: `DELETE /api/task-runs` and show progress via WS
- Global cookies editor: GET/PUT `/api/settings/douyin`

- [ ] **Step 3: Add delete-by-video button in History Reports list**

Add a delete icon/button per report row:
- confirm modal
- call `DELETE /api/videos/{video_id}`
- refresh reports list

- [ ] **Step 4: UI regression checks**

Manual:
- Reports still render
- Global settings still works
- Data Management buttons show confirmation modals

- [ ] **Step 5: Commit**

```bash
git add visual-companion/src/App.tsx
git commit -m "feat(ui): add data management and ws json log support"
```

---

## Task 12: End-to-end regression checklist

- [ ] **Step 1: Run test suite**

Run: `pytest -q`
Expected: PASS

- [ ] **Step 2: Smoke test servers**

- Start backend: `python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000`
- Start frontend: `cd visual-companion && npm run dev -- --host 0.0.0.0 --port 5174`

- [ ] **Step 3: Manual UI flow**

- Set Douyin cookies via Data Management
- Run task depth=1
- Confirm:
  - reports appear in History Reports
  - task run appears in Task Runs list
  - delete run removes summaries/threads but keeps videos
  - delete video removes everything
  - delete all runs returns task_id and streams progress logs

- [ ] **Step 4: Final docs update**

Add a short operator section to `README.md` describing:
- how to set cookies
- how to run delete operations safely

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: add operator notes for cookies and data management"
```

