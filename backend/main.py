import os
import asyncio
import json
from typing import List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import sessionmaker
from backend.database.models import get_engine, create_tables, Video, Thread, Summary
from backend.scrapers.douyin import DouyinScraper
from backend.pipeline.run_analysis import AnalysisPipeline

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

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # 保持连接，等待客户端消息（如果需要双向通信）
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/api/reports")
async def get_reports(limit: int = 10):
    with SessionLocal() as db:
        reports = db.query(Summary).order_by(Summary.created_at.desc()).limit(limit).all()
        return [
            {
                "id": r.id,
                "video_id": r.video_id,
                "markdown": r.report_markdown,
                "created_at": r.created_at
            }
            for r in reports if r.report_markdown
        ]

@app.post("/api/task/start")
async def start_task(config: dict):
    """
    触发任务接口，通过后台任务执行 Pipeline，并使用 WS 广播日志。
    """
    global task_running
    # check if lock is already acquired without blocking
    if task_lock.locked() or task_running:
        return {"status": "Task rejected", "reason": "Another task is running"}
        
    asyncio.create_task(real_pipeline_execution(config))
    return {"status": "Task started", "config": config}

async def real_pipeline_execution(config: dict):
    global task_running
    async with task_lock:
        task_running = True
        try:
            await _real_pipeline_execution(config)
        finally:
            task_running = False

async def _real_pipeline_execution(config: dict):
    platform = config.get("platform", "抖音")
    keyword = config.get("keyword", "Python")
    depth = int(config.get("depth", 2))
    
    await manager.broadcast(f"[INFO] 初始化 {platform} Playwright 爬虫...")
    scraper = DouyinScraper()
    
    try:
        try:
            await asyncio.wait_for(scraper.start_browser(headless=True), timeout=30)
        except Exception as e:
            await manager.broadcast(f"[ERROR] 浏览器启动失败: {str(e)}")
            await manager.broadcast("[HINT] 如果是缺少系统依赖，请在服务器执行: playwright install-deps chromium")
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
                
                # 2. 抓取并存入评论
                comments_data = await scraper.fetch_comments(v_data['url'], 5)
                for c_data in comments_data:
                    # 去重检查：避免多次执行任务时数据库堆积重复评论
                    existing_thread = db.query(Thread).filter_by(
                        video_id=video.id, 
                        root_comment=c_data['root_comment']
                    ).first()
                    
                    if not existing_thread:
                        thread = Thread(
                            video_id=video.id,
                            root_comment=c_data['root_comment'],
                            replies_json=json.dumps(c_data['replies'])
                        )
                        db.add(thread)
                db.commit()
                
                # 3. 触发分析流（ASR/OCR -> LLM -> Markdown）
                await manager.broadcast(f"[LLM] 调用分析流水线生成报告...")
                report_md = pipeline.run_for_video(video.id, "dummy.mp4")
                
                await manager.broadcast(f"[SUCCESS] 视频 '{v_data['title']}' 处理完成！\n预览：\n{report_md[:100]}...")
                
    except Exception as e:
        await manager.broadcast(f"[ERROR] 发生异常: {str(e)}")
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
