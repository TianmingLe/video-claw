# video-claw / OmniScraper Pro

这是一个“抓取 → 分析 → 报告 → 数据管理”的前后端项目：

- 后端：FastAPI + SQLAlchemy + SQLite（提供 `/api/*` 与 `/ws`）
- 前端：React + Vite（一个可视化操作台，任务启动、日志、报告与数据管理）

## 快速开始

### 1) 安装依赖

后端：

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m playwright install-deps chromium
```

前端：

```bash
cd visual-companion
npm install --ignore-scripts
```

### 2) 启动服务

后端：

```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

前端：

```bash
cd visual-companion
npm run dev -- --host 0.0.0.0 --port 4173
```

### 3) 打开入口

- 前端 UI：`http://localhost:4173/`
- 后端 Swagger：`http://localhost:8000/docs`

说明：

- 如果你打开的是 `8000/docs`，你看到的是 API 文档（后端），不是前端 UI。
- 前端已配置代理（见 [vite.config.mts](file:///workspace/visual-companion/vite.config.mts)），会把 `/api` 与 `/ws` 转发到 `127.0.0.1:8000`，因此正常情况下不需要手动改后端地址。

## 文档

- 设计文档：[2026-04-16-data-management-and-douyin-ui-scrape-design.md](file:///workspace/docs/superpowers/specs/2026-04-16-data-management-and-douyin-ui-scrape-design.md)
- 实现计划：[2026-04-16-data-management-ws-logs-douyin-ui-implementation.md](file:///workspace/docs/superpowers/plans/2026-04-16-data-management-ws-logs-douyin-ui-implementation.md)
