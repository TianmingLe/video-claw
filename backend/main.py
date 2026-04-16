import os
import asyncio
import json
from typing import List
import uuid
import time
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import sessionmaker
from backend.database.models import get_engine, create_tables, Video, Thread, Summary, TaskRun, TaskRunVideo
from backend.scrapers.douyin import DouyinScraper
from backend.pipeline.run_analysis import AnalysisPipeline
from backend.ws.logging import build_ws_log
from backend.settings.store import SettingsStore
from backend.admin.data_management import clear_reports_content, delete_run_outputs, delete_video_global

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 使用环境变量或默认路径配置 DB
DB_PATH = os.getenv("DB_PATH", "sqlite:///omniscraper_real.db")
engine = get_engine(DB_PATH)
create_tables(engine)
SessionLocal = sessionmaker(bind=engine)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        dead: List[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                dead.append(connection)
        for d in dead:
            self.disconnect(d)

manager = ConnectionManager()
task_lock = asyncio.Lock()
task_running = False
admin_jobs: dict[str, dict] = {}

async def ws_log(
    *,
    level: str,
    module: str,
    msg: str,
    reason: str | None = None,
    run_id: int | None = None,
    video_id: str | None = None,
    metrics: dict | None = None,
    counts: dict | None = None,
):
    await manager.broadcast(
        build_ws_log(
            level=level,
            module=module,
            msg=msg,
            reason=reason,
            run_id=run_id,
            video_id=video_id,
            metrics=metrics,
            counts=counts,
        )
    )

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # 保持连接，等待客户端消息（如果需要双向通信）
            await websocket.receive_text()
    except Exception:
        # Catch any exception including WebSocketDisconnect, ConnectionClosedError
        pass
    finally:
        manager.disconnect(websocket)

@app.get("/api/reports")
async def get_reports(limit: int = 10):
    with SessionLocal() as db:
        reports = db.query(Summary).order_by(Summary.id.desc()).limit(limit).all()
        return [
            {
                "id": r.id,
                "video_id": r.video_id,
                "markdown": r.report_markdown,
                "created_at": None
            }
            for r in reports if r.report_markdown
        ]

@app.post("/api/admin/reports/clear")
async def clear_reports():
    with SessionLocal() as db:
        cleared_count = clear_reports_content(db)
    await ws_log(level="ADMIN", module="data_admin", msg="已清空报告内容", counts={"summaries": cleared_count})
    return {"cleared_count": cleared_count}

@app.get("/api/task-runs")
async def get_task_runs(limit: int = 20):
    with SessionLocal() as db:
        runs = db.query(TaskRun).order_by(TaskRun.id.desc()).limit(limit).all()
        return [
            {
                "id": r.id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "platform": r.platform,
                "keyword": r.keyword,
                "depth": r.depth,
                "status": r.status,
                "error_code": r.error_code,
                "duration_ms": r.duration_ms,
            }
            for r in runs
        ]

@app.delete("/api/task-runs/{run_id}")
async def delete_task_run(run_id: int):
    with SessionLocal() as db:
        counts = delete_run_outputs(db, run_id)
    await ws_log(level="ADMIN", module="data_admin", msg="已删除任务结果", run_id=run_id, counts=counts)
    return {"deleted": counts}

@app.delete("/api/task-runs")
async def delete_all_task_runs(batch_size: int = 100):
    task_id = uuid.uuid4().hex
    admin_jobs[task_id] = {"status": "running", "counts": {}}

    async def run_job():
        total = {"task_run_videos": 0, "threads": 0, "summaries": 0, "task_runs": 0}
        try:
            while True:
                with SessionLocal() as db:
                    run_ids = [r[0] for r in db.query(TaskRun.id).order_by(TaskRun.id.asc()).limit(batch_size).all()]
                if not run_ids:
                    break

                for rid in run_ids:
                    with SessionLocal() as db:
                        counts = delete_run_outputs(db, int(rid))
                    for k, v in counts.items():
                        total[k] = total.get(k, 0) + int(v)
                    await ws_log(
                        level="ADMIN",
                        module="data_admin",
                        msg="批次删除任务结果中",
                        run_id=int(rid),
                        counts={"task_id": task_id, **total},
                    )

            admin_jobs[task_id] = {"status": "success", "counts": total}
            await ws_log(level="ADMIN", module="data_admin", msg="一键删除任务结果完成", counts={"task_id": task_id, **total})
        except Exception as e:
            admin_jobs[task_id] = {"status": "failed", "error": str(e), "counts": total}
            await ws_log(level="ERROR", module="data_admin", msg="一键删除任务结果失败", reason="DELETE_FAILED", counts={"task_id": task_id, **total})

    asyncio.create_task(run_job())
    return {"task_id": task_id}

@app.get("/api/admin/tasks/{task_id}")
async def get_admin_task(task_id: str):
    return admin_jobs.get(task_id, {"status": "not_found"})

@app.delete("/api/videos/{video_id}")
async def delete_video(video_id: str):
    with SessionLocal() as db:
        counts = delete_video_global(db, video_id)
    await ws_log(level="ADMIN", module="data_admin", msg="已删除视频全部数据", video_id=video_id, counts=counts)
    return {"deleted": counts}

@app.post("/api/admin/db/vacuum")
async def vacuum_db():
    task_id = uuid.uuid4().hex
    admin_jobs[task_id] = {"status": "running"}

    async def run_job():
        try:
            await ws_log(level="ADMIN", module="db", msg="开始 VACUUM", counts={"task_id": task_id})
            if engine.dialect.name == "sqlite":
                with engine.connect() as conn:
                    conn.exec_driver_sql("VACUUM")
            admin_jobs[task_id] = {"status": "success"}
            await ws_log(level="ADMIN", module="db", msg="VACUUM 完成", counts={"task_id": task_id})
        except Exception as e:
            admin_jobs[task_id] = {"status": "failed", "error": str(e)}
            await ws_log(level="ERROR", module="db", msg="VACUUM 失败", reason="VACUUM_FAILED", counts={"task_id": task_id})

    asyncio.create_task(run_job())
    return {"task_id": task_id}

@app.get("/api/settings/douyin")
async def get_douyin_settings():
    with SessionLocal() as db:
        store = SettingsStore(db)
        settings = store.get_json("douyin.settings")
        cookies = settings.get("cookies")
        ua_pool = settings.get("user_agent_pool")
        cookies_count = len(cookies) if isinstance(cookies, list) else 0
        ua_pool_count = len(ua_pool) if isinstance(ua_pool, list) else 0
        return {
            "has_cookies": cookies_count > 0,
            "cookies_count": cookies_count,
            "user_agent_pool_count": ua_pool_count,
        }

@app.put("/api/settings/douyin")
async def put_douyin_settings(payload: dict):
    with SessionLocal() as db:
        store = SettingsStore(db)
        store.set_json("douyin.settings", payload)
    await ws_log(level="ADMIN", module="settings", msg="已更新抖音全局配置")
    return {"status": "ok"}

@app.post("/api/task/start")
async def start_task(config: dict):
    """
    触发任务接口，通过后台任务执行 Pipeline，并使用 WS 广播日志。
    """
    global task_running
    # check if lock is already acquired without blocking
    if task_lock.locked() or task_running:
        return {"status": "Task rejected", "reason": "Another task is running"}

    platform = config.get("platform", "抖音")
    keyword = config.get("keyword", "Python")
    depth = int(config.get("depth", 2))
    config_snapshot = dict(config)
    config_snapshot.pop("llm_api_key", None)
    config_snapshot.pop("vlm_api_key", None)

    with SessionLocal() as db:
        run = TaskRun(
            platform=platform,
            keyword=keyword,
            depth=depth,
            status="running",
            started_at=datetime.utcnow(),
            config_json=json.dumps(config_snapshot, ensure_ascii=False),
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        config["run_id"] = run.id

    task_running = True
    asyncio.create_task(real_pipeline_execution(config))
    await ws_log(level="INFO", module="task", msg="任务已创建", run_id=config.get("run_id"))
    return {"status": "Task started", "config": config, "run_id": config.get("run_id")}

async def real_pipeline_execution(config: dict):
    global task_running
    async with task_lock:
        try:
            await _real_pipeline_execution(config)
        finally:
            task_running = False

async def _real_pipeline_execution(config: dict):
    platform = config.get("platform", "抖音")
    keyword = config.get("keyword", "Python")
    depth = int(config.get("depth", 2))
    run_id = config.get("run_id")
    started_monotonic = time.monotonic()
    
    await manager.broadcast(f"[INFO] 初始化 {platform} Playwright 爬虫...")
    scraper = DouyinScraper()
    
    try:
        try:
            await asyncio.wait_for(scraper.start_browser(headless=True), timeout=30)
        except Exception as e:
            await manager.broadcast(f"[ERROR] 浏览器启动失败: {str(e)}")
            await manager.broadcast("[HINT] 如果是缺少系统依赖，请在服务器执行: playwright install-deps chromium")
            if run_id is not None:
                with SessionLocal() as db:
                    db.query(TaskRun).filter_by(id=run_id).update(
                        {
                            "status": "failed",
                            "error_code": "BROWSER_LAUNCH_FAILED",
                            "finished_at": datetime.utcnow(),
                            "duration_ms": int((time.monotonic() - started_monotonic) * 1000),
                        }
                    )
                    db.commit()
            return
        await manager.broadcast("[INFO] 浏览器已启动，开始进入搜索页...")
        await manager.broadcast(f"[INFO] 正在搜索关键词 '{keyword}' (Top {depth})...")
        videos_data = await scraper.search_videos(keyword, depth)
        
        if not videos_data:
            await manager.broadcast("[WARNING] 未找到任何视频数据，任务提前结束。")
            return
            
        await manager.broadcast(f"[SUCCESS] 找到 {len(videos_data)} 个视频，开始抓取评论并入库...")
        
        with SessionLocal() as db:
            # 传递整个 config 进入 Pipeline，使得内部能感知到 LLM/VLM 配置
            pipeline = AnalysisPipeline(db, config=config)
            
            for i, v_data in enumerate(videos_data):
                await manager.broadcast(f"[PROGRESS] 处理视频 {i+1}/{len(videos_data)}: {v_data['title']}")
                
                # 1. 视频入库
                video = db.query(Video).filter_by(id=v_data['id']).first()
                if not video:
                    video = Video(
                        id=v_data['id'], platform=v_data['platform'],
                        url=v_data['url'], title=v_data['title'],
                        author=v_data['author'], like_count=v_data['like_count']
                    )
                    db.add(video)
                    db.commit()

                if run_id is not None:
                    exists = db.query(TaskRunVideo).filter_by(run_id=run_id, video_id=video.id).first()
                    if not exists:
                        db.add(TaskRunVideo(run_id=run_id, video_id=video.id))
                        db.commit()
                
                # 2. 抓取并存入评论
                comments_data = await scraper.fetch_comments(v_data['url'], 5)
                for c_data in comments_data:
                    # 去重检查：避免多次执行任务时数据库堆积重复评论
                    existing_thread = db.query(Thread).filter_by(video_id=video.id, root_comment=c_data["root_comment"], run_id=run_id).first()
                    
                    if not existing_thread:
                        thread = Thread(
                            video_id=video.id,
                            root_comment=c_data['root_comment'],
                            replies_json=json.dumps(c_data['replies']),
                            run_id=run_id,
                        )
                        db.add(thread)
                db.commit()
                
                # 3. 触发分析流（ASR/OCR -> LLM -> Markdown）
                await manager.broadcast(f"[LLM] 调用分析流水线生成报告...")

                heartbeat_task = None
                timed_out = False
                try:
                    async def heartbeat():
                        while True:
                            await asyncio.sleep(10)
                            await manager.broadcast("[PROGRESS] 分析中，请稍候...")

                    heartbeat_task = asyncio.create_task(heartbeat())
                    try:
                        report_md = await asyncio.wait_for(
                            asyncio.to_thread(pipeline.run_for_video, video.id, "dummy.mp4"),
                            timeout=float(config.get("pipeline_timeout_seconds", 300)),
                        )
                    except asyncio.TimeoutError:
                        timed_out = True
                finally:
                    if heartbeat_task:
                        heartbeat_task.cancel()

                if timed_out:
                    await manager.broadcast(f"[ERROR] 视频 '{v_data['title']}' 分析超时，已跳过。")
                    continue
                
                await manager.broadcast(f"[SUCCESS] 视频 '{v_data['title']}' 处理完成！\n预览：\n{report_md[:100]}...")
        if run_id is not None:
            with SessionLocal() as db:
                db.query(TaskRun).filter_by(id=run_id).update(
                    {
                        "status": "success",
                        "finished_at": datetime.utcnow(),
                        "duration_ms": int((time.monotonic() - started_monotonic) * 1000),
                    }
                )
                db.commit()
    except Exception as e:
        await manager.broadcast(f"[ERROR] 发生异常: {str(e)}")
        if run_id is not None:
            with SessionLocal() as db:
                db.query(TaskRun).filter_by(id=run_id).update(
                    {
                        "status": "failed",
                        "error_code": "PIPELINE_FAILED",
                        "finished_at": datetime.utcnow(),
                        "duration_ms": int((time.monotonic() - started_monotonic) * 1000),
                    }
                )
                db.commit()
    finally:
        await scraper.close_browser()
        await manager.broadcast(f"[INFO] 爬虫资源已释放，任务结束。")

import uvicorn
import socket

def get_free_port(default_port=8000):
    # Try to get default port, else find a free port
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", default_port))
        s.close()
        return default_port
    except OSError:
        s.close()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        return port

if __name__ == "__main__":
    port = get_free_port(8000)
    print(f"Starting server on port {port}")
    uvicorn.run(app, host="127.0.0.1", port=port)
