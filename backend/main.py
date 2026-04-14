import asyncio
from typing import List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    (Phase 3 MVP: 使用 asyncio 模拟耗时任务与日志流)
    """
    asyncio.create_task(mock_pipeline_execution(config))
    return {"status": "Task started", "config": config}

async def mock_pipeline_execution(config: dict):
    platform = config.get("platform", "Unknown")
    await manager.broadcast(f"[INFO] 正在初始化 {platform} 爬虫引擎...")
    await asyncio.sleep(1)
    await manager.broadcast(f"[INFO] 开始采集视频，目标深度 {config.get('depth', 100)}...")
    
    for i in range(1, 4):
        await asyncio.sleep(1.5)
        await manager.broadcast(f"[PROGRESS] 已处理第 {i} 个视频数据...")
        
    await manager.broadcast(f"[LLM] 调用 OpenAI 接口生成知识点总结...")
    await asyncio.sleep(2)
    await manager.broadcast(f"[SUCCESS] 任务完成！已导出 Markdown 报告。")

if __name__ == "__main__":
    import uvicorn
    # 为了方便桌面端，MVP 阶段绑定固定端口 8000
    uvicorn.run(app, host="127.0.0.1", port=8000)