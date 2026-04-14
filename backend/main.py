import asyncio
import json
from typing import List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import sessionmaker
from backend.database.models import get_engine, create_tables, Video, Thread
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

# 全局初始化 DB
engine = get_engine("sqlite:///omniscraper_real.db")
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
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # 保持连接，等待客户端消息（如果需要双向通信）
            data = await websocket.receive_text()
            await manager.broadcast(f"Echo: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/api/task/start")
async def start_task(config: dict):
    """
    触发任务接口，通过后台任务执行 Pipeline，并使用 WS 广播日志。
    """
    asyncio.create_task(real_pipeline_execution(config))
    return {"status": "Task started", "config": config}

async def real_pipeline_execution(config: dict):
    platform = config.get("platform", "抖音")
    keyword = config.get("keyword", "Python")
    depth = int(config.get("depth", 2))
    
    await manager.broadcast(f"[INFO] 初始化 {platform} Playwright 爬虫...")
    scraper = DouyinScraper()
    await scraper.start_browser(headless=True)
    
    try:
        await manager.broadcast(f"[INFO] 正在搜索关键词 '{keyword}' (Top {depth})...")
        videos_data = await scraper.search_videos(keyword, depth)
        await manager.broadcast(f"[SUCCESS] 找到 {len(videos_data)} 个视频，开始抓取评论并入库...")
        
        with SessionLocal() as db:
            pipeline = AnalysisPipeline(db)
            
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

if __name__ == "__main__":
    import uvicorn
    # 为了方便桌面端，MVP 阶段绑定固定端口 8000
    uvicorn.run(app, host="127.0.0.1", port=8000)