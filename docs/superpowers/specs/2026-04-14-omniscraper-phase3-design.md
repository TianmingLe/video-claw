# OmniScraper Pro Phase 3: 桌面端架构与前后端通信 (Spec)

## 1. 目标与范围 (Scope)

Phase 3 旨在将此前已实现的核心引擎和分析流水线，与纯静态的 React 前端 (`visual-companion`) 有机结合，并包裹进 **Electron** 桌面端外壳中。

**核心目标：**
1. 建立一个稳定的 **FastAPI + WebSocket** 后端服务，负责接收前端任务指令，并向前端推送实时执行日志与进度。
2. 重构前端 React 项目，使其具备与 Python 后端通信的能力。
3. 引入 Electron 作为桌面壳，管理 Python 子进程的生命周期，并预研 `electron-builder` 打包配置。

**设计原则：**
- **前后端解耦**：Electron/React 仅负责渲染 UI 和配置持久化，爬虫、存储、分析全部交由 Python 服务。
- **生命周期一致**：Electron 启动时启动 Python FastAPI，Electron 退出时优雅杀死 Python 进程。
- **无感体验**：本地接口优先绑定动态可用端口（或固定如 8000，但在真实发布时应处理端口冲突，MVP 阶段简化为固定端口）。

## 2. 架构与通信机制

采用 **HTTP (FastAPI) + WebSocket** 的双通道通信：

*   **HTTP REST API**：
    *   用于触发单次调用（如：提交任务配置 `POST /api/task/start`，获取历史任务列表 `GET /api/tasks`）。
*   **WebSocket (WS)**：
    *   用于建立长连接 (`ws://localhost:8000/ws`)。
    *   Python 在执行 pipeline 时，将实时日志（如 `[INFO] 正在抓取第 1/10 个视频`）通过该连接 push 给 React 前端进行展示。

## 3. 模块详细设计

### 3.1 Python 后端入口 (`backend/main.py`)
*   使用 `fastapi` 和 `uvicorn` 构建 Web 服务器。
*   提供 `/api/task/start` 接口，接收如平台、关键词、采集深度等参数。
*   实现 `/ws` WebSocket 路由，维护一个连接管理器 (`ConnectionManager`)。
*   将原有的 `AnalysisPipeline` 放入异步任务中执行，执行过程中通过 manager 将 log 推给所有活跃的 ws 连接。

### 3.2 Electron 外壳配置 (`visual-companion/electron/`)
由于目前的 `visual-companion` 是标准的 Vite React 模板，需做以下改动：
*   **依赖安装**：引入 `electron`, `electron-builder`, `concurrently` (开发用), `wait-on`。
*   **`main.js`**: Electron 主进程脚本。
    *   创建 `BrowserWindow`。
    *   开发环境下加载 `http://localhost:5173`。
    *   生产环境下加载打包后的 `dist/index.html`。
    *   **进程管理**：使用 `child_process.spawn` 启动 `python backend/main.py`（MVP阶段假设运行环境中已有 python；后续可通过 PyInstaller 打包独立的 python exe）。
*   **`preload.js`**（可选）：暴露必要的系统级别 API 给 React（如文件选择、版本号等），当前 MVP 阶段如无必要可简化。

### 3.3 React 前端重构 (`visual-companion/src/`)
*   增加一个状态管理（可简单用 `useState` / `useRef`）维护 WebSocket 连接。
*   将静态的“新建任务”按钮修改为真实的 `POST` 请求（请求 `localhost:8000/api/task/start`）。
*   将底部的“运行方式”或“终端面板”修改为一个真正的 Log 控制台组件 (`LogConsole`)，实时渲染来自 WS 的字符串流。

## 4. 依赖变更

*   **Python**: `fastapi`, `uvicorn`, `websockets`。
*   **Node.js**: `electron` (dev), `electron-builder` (dev), `concurrently` (dev), `wait-on` (dev)。

## 5. 测试与验收标准

*   执行 `npm run electron:dev` 后，应自动启动 Python FastAPI 服务（终端可见 uvicorn 启动日志），并随后弹出一个原生的桌面窗口展示 React UI。
*   在 UI 点击“新建任务”，UI 底部的终端面板能实时打印出 Python 传来的模拟分析日志。
*   关闭 Electron 窗口时，后台的 Python 服务被正确终止，不留僵尸进程。