# OmniScraper Pro Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭建基于 FastAPI+WebSocket 的 Python 后端，集成 Electron 桌面端，并实现 React 前后端实时日志联调通信。

**Architecture:** Python 后端使用 FastAPI 提供 HTTP 接口触发爬虫与分析任务，使用 WebSockets 向连接的客户端（Electron/React）推送实时进度与日志。前端使用 React 构建，配置为 Electron 的渲染进程；主进程 (Node.js) 负责启动和结束 Python 子进程，从而实现桌面端应用的生命周期闭环。

**Tech Stack:** Python 3.10 (FastAPI, uvicorn), Node.js (Electron, electron-builder, concurrently), React (Vite, Tailwind)

---

### Task 1: 搭建 Python FastAPI + WebSocket 后端服务

**Files:**
- Modify: `requirements.txt`
- Create: `backend/main.py`

- [ ] **Step 1: 安装 FastAPI 依赖**

修改 `requirements.txt`，添加 `fastapi`, `uvicorn`, `websockets`。
```text
sqlalchemy>=2.0.0
pytest>=7.0.0
pytest-asyncio>=0.21.0
playwright>=1.40.0
pydantic>=2.0.0
fastapi>=0.100.0
uvicorn>=0.23.0
websockets>=11.0.3
```

- [ ] **Step 2: 实现 FastAPI 主程序**

创建 `backend/main.py`：
```python
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
```

- [ ] **Step 3: 运行并验证**
```bash
pip install -r requirements.txt
# (无需单独在此步骤挂起验证，将在后续联合启动时测试)
```

- [ ] **Step 4: 提交代码**
```bash
git add requirements.txt backend/main.py
git commit -m "feat: add fastapi and websocket server for python backend"
```

---

### Task 2: 配置 Electron 外壳与主进程通信逻辑

**Files:**
- Modify: `visual-companion/package.json`
- Create: `visual-companion/electron/main.js`

- [ ] **Step 1: 安装 Electron 相关依赖**

在 `visual-companion` 目录下：
```bash
cd visual-companion
npm install electron concurrently wait-on cross-env --save-dev
npm install electron-is-dev --save
```

- [ ] **Step 2: 修改 package.json 以支持 Electron**

在 `visual-companion/package.json` 中：
1. 移除 `"type": "module"` （Electron 主进程目前以 CommonJS 方式运行最稳定，为避免配置混乱，移除该字段）。如果遇到 Vite 报错，我们将配置 Vite 输出格式。
2. 添加 `"main": "electron/main.js"`
3. 修改 `scripts`：
```json
  "main": "electron/main.js",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "lint": "eslint .",
    "preview": "vite preview",
    "electron:dev": "concurrently -k \"cross-env BROWSER=none npm run dev\" \"wait-on http://127.0.0.1:5173 && electron .\"",
    "start": "npm run electron:dev"
  }
```

*注意：移除 `type: "module"` 后，需要修改 `vite.config.ts`、`eslint.config.js` 为 CommonJS，或者将其重命名为 `.mjs`/`.mts`。在此方案中，我们直接重命名文件以解决兼容问题。*

- [ ] **Step 3: 解决模块化文件重命名**

执行命令重命名 Vite 配置文件，以允许 `package.json` 没有 `type: module` 时的正确执行：
```bash
cd visual-companion
mv vite.config.ts vite.config.mts
```

- [ ] **Step 4: 创建 Electron 主进程文件**

创建 `visual-companion/electron/main.js`：
```javascript
const { app, BrowserWindow } = require('electron');
const path = require('path');
const isDev = require('electron-is-dev');
const { spawn } = require('child_process');

let mainWindow;
let pythonProcess = null;

function startPythonBackend() {
  // 在真实打包时需要判断环境，这里假设使用本地 python
  const pythonPath = 'python';
  // 指定 backend/main.py 的相对路径 (假设执行在 workspace 根或 visual-companion 目录下)
  const scriptPath = path.join(__dirname, '..', '..', 'backend', 'main.py');
  
  pythonProcess = spawn(pythonPath, [scriptPath], {
    cwd: path.join(__dirname, '..', '..') // 确保在 workspace 根目录运行
  });

  pythonProcess.stdout.on('data', (data) => {
    console.log(`[Python] ${data.toString()}`);
  });

  pythonProcess.stderr.on('data', (data) => {
    console.error(`[Python Err] ${data.toString()}`);
  });

  pythonProcess.on('close', (code) => {
    console.log(`Python process exited with code ${code}`);
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    }
  });

  const url = isDev 
    ? 'http://127.0.0.1:5173' 
    : `file://${path.join(__dirname, '../dist/index.html')}`;

  mainWindow.loadURL(url);

  if (isDev) {
    mainWindow.webContents.openDevTools();
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.on('ready', () => {
  startPythonBackend();
  createWindow();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('will-quit', () => {
  // 优雅杀死 Python 子进程
  if (pythonProcess) {
    pythonProcess.kill('SIGINT');
  }
});

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow();
  }
});
```

- [ ] **Step 5: 提交代码**
```bash
git add visual-companion/package.json visual-companion/electron/main.js visual-companion/vite.config.mts visual-companion/vite.config.ts
git commit -m "feat: setup electron shell and python process lifecycle management"
```

---

### Task 3: 前端 React 接入 WebSocket 与控制逻辑

**Files:**
- Modify: `visual-companion/src/App.tsx`

- [ ] **Step 1: 在 React 中接入状态与 WebSocket**

修改 `visual-companion/src/App.tsx`，将现有的静态组件改为可以连接 WS 并渲染日志的动态组件：
```tsx
import { useState, useEffect, useRef } from 'react';
import {
  Search, Settings, Play, Clock, FileJson, FileSpreadsheet,
  Database, BarChart, Terminal, Download, Bot, ShieldAlert, Video
} from 'lucide-react';

export default function App() {
  const [logs, setLogs] = useState<string[]>(['[System] OmniScraper Pro Initialized.']);
  const [isRunning, setIsRunning] = useState(false);
  const [platform, setPlatform] = useState('抖音');
  const wsRef = useRef<WebSocket | null>(null);
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // 连接到 Python 后端的 WebSocket
    const ws = new WebSocket('ws://127.0.0.1:8000/ws');
    ws.onopen = () => setLogs(prev => [...prev, '[System] Connected to Python Engine.']);
    ws.onmessage = (event) => {
      setLogs(prev => [...prev, event.data]);
      if (event.data.includes('[SUCCESS]')) {
        setIsRunning(false);
      }
    };
    ws.onerror = () => setLogs(prev => [...prev, '[Error] Failed to connect to Engine.']);
    ws.onclose = () => setLogs(prev => [...prev, '[System] Disconnected.']);
    
    wsRef.current = ws;
    return () => ws.close();
  }, []);

  useEffect(() => {
    // 自动滚动到最新日志
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const handleStartTask = async () => {
    if (isRunning) return;
    setIsRunning(true);
    setLogs(prev => [...prev, '\n--- Starting New Task ---']);
    
    try {
      const response = await fetch('http://127.0.0.1:8000/api/task/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ platform, depth: 100 })
      });
      if (!response.ok) throw new Error('Network response was not ok');
    } catch (err) {
      setLogs(prev => [...prev, `[Error] Failed to trigger task: ${err}`]);
      setIsRunning(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8 font-sans">
      <div className="max-w-6xl mx-auto space-y-8">
        
        <header className="flex items-center justify-between bg-white p-6 rounded-xl shadow-sm border border-gray-100">
          <div className="flex items-center gap-3">
            <div className="bg-blue-600 p-2 rounded-lg">
              <Bot className="text-white w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">OmniScraper Pro</h1>
              <p className="text-sm text-gray-500">全平台视频与评论智能采集分析系统</p>
            </div>
          </div>
          <div className="flex gap-4">
            <button className="flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors">
              <Settings className="w-4 h-4" />
              全局设置
            </button>
            <button 
              onClick={handleStartTask}
              disabled={isRunning}
              className={`flex items-center gap-2 px-4 py-2 ${isRunning ? 'bg-gray-400' : 'bg-blue-600 hover:bg-blue-700'} text-white rounded-lg transition-colors shadow-sm`}
            >
              <Play className="w-4 h-4" />
              {isRunning ? '任务执行中...' : '新建任务'}
            </button>
          </div>
        </header>

        <div className="grid grid-cols-3 gap-6">
          <div className="col-span-2 space-y-6">
            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
              <h2 className="text-lg font-semibold mb-4 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Search className="w-5 h-5 text-blue-500" />
                  基础采集配置
                </div>
                <div className="flex items-center gap-1 text-xs text-amber-600 bg-amber-50 px-2 py-1 rounded">
                  <ShieldAlert className="w-3 h-3" />
                  内置智能限速与防风控策略
                </div>
              </h2>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">目标平台</label>
                  <div className="flex gap-3">
                    {['抖音', '小红书', 'Bilibili', 'YouTube', '快手'].map(p => (
                      <label key={p} className="flex items-center gap-2 p-2 border rounded-lg cursor-pointer hover:bg-gray-50">
                        <input 
                          type="radio" 
                          name="platform" 
                          checked={platform === p} 
                          onChange={() => setPlatform(p)}
                          className="text-blue-600" 
                        />
                        <span className="text-sm">{p}</span>
                      </label>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">搜索关键词 (支持多个，换行分隔)</label>
                  <textarea 
                    className="w-full border border-gray-300 rounded-lg p-3 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    rows={2}
                    defaultValue="Python教程&#10;自媒体运营"
                  />
                </div>
                
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">视频采集数量</label>
                    <input type="number" defaultValue={100} className="w-full border border-gray-300 rounded-lg p-2.5" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">一级评论深度</label>
                    <input type="number" defaultValue={200} className="w-full border border-gray-300 rounded-lg p-2.5" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">回复深度</label>
                    <input type="number" defaultValue={20} className="w-full border border-gray-300 rounded-lg p-2.5" />
                  </div>
                </div>
              </div>
            </div>
            
            <div className="bg-gray-900 p-6 rounded-xl shadow-sm border border-gray-800 text-gray-300 h-64 flex flex-col">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2 text-white shrink-0">
                <Terminal className="w-5 h-5 text-green-400" />
                执行日志 (Console)
              </h2>
              <div className="flex-1 overflow-y-auto font-mono text-sm space-y-1 p-2 bg-black/50 rounded border border-gray-700">
                {logs.map((log, i) => (
                  <div key={i} className={`${log.includes('[Error]') ? 'text-red-400' : log.includes('[SUCCESS]') ? 'text-green-400' : 'text-gray-300'}`}>
                    {log}
                  </div>
                ))}
                <div ref={logEndRef} />
              </div>
            </div>

          </div>

          <div className="space-y-6">
            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Download className="w-5 h-5 text-green-500" />
                数据输出格式
              </h2>
              <div className="space-y-3">
                <label className="flex items-center gap-3 p-3 border rounded-lg hover:bg-gray-50 cursor-pointer">
                  <Database className="w-5 h-5 text-gray-500" />
                  <div className="flex-1">
                    <div className="font-medium text-sm">SQLite 数据库</div>
                  </div>
                  <input type="checkbox" defaultChecked className="text-blue-600 rounded" />
                </label>
                <label className="flex items-center gap-3 p-3 border rounded-lg hover:bg-gray-50 cursor-pointer border-blue-200 bg-blue-50">
                  <BarChart className="w-5 h-5 text-blue-600" />
                  <div className="flex-1">
                    <div className="font-medium text-sm">Markdown 分析报告</div>
                  </div>
                  <input type="checkbox" defaultChecked className="text-blue-600 rounded" />
                </label>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 提交代码**
```bash
git add visual-companion/src/App.tsx
git commit -m "feat: integrate frontend react with python backend via websockets and http"
```

---

### Task 4: electron-builder 打包预研与联调验证

**Files:**
- Modify: `visual-companion/package.json`

- [ ] **Step 1: 添加 build 配置预研**

修改 `visual-companion/package.json`，追加 `build` 对象：
```json
  "build": {
    "appId": "com.omniscraper.pro",
    "productName": "OmniScraper Pro",
    "directories": {
      "output": "release"
    },
    "files": [
      "dist/**/*",
      "electron/**/*",
      "package.json"
    ],
    "mac": {
      "target": ["dmg"]
    },
    "win": {
      "target": ["nsis"]
    },
    "linux": {
      "target": ["AppImage"]
    }
  },
```

- [ ] **Step 2: 修改 ESLint 配置以支持 CommonJS**

由于我们将 `package.json` 中的 `type: module` 移除了，你需要将 `eslint.config.js` 重命名为 `eslint.config.mjs`，或者暂时禁用 ESLint 以确保构建成功。
```bash
cd visual-companion
mv eslint.config.js eslint.config.mjs
```

- [ ] **Step 3: 执行全链路测试构建**
```bash
cd visual-companion
npm run build
```
Expected: vite build 成功完成，无报错。

*(注意：在真实的无头终端 CI 环境中运行 `npm run electron:dev` 会因为缺少显示器 GUI 支持而失败，所以我们仅验证构建是否通过。桌面端的功能将在真实电脑上运行。)*

- [ ] **Step 4: 提交代码**
```bash
git add visual-companion/package.json visual-companion/eslint.config.mjs visual-companion/eslint.config.js
git commit -m "feat: configure electron-builder and resolve cjs/mjs build compatibility"
```