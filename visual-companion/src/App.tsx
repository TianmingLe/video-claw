import { useState, useEffect, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Search, Settings, Play, Database, BarChart, Terminal, Download, Bot, ShieldAlert, FileText, X, Trash2
} from 'lucide-react';

type ReportItem = {
  id: number;
  video_id: string;
  markdown: string;
  created_at: string;
};

type TaskRunItem = {
  id: number;
  created_at: string | null;
  platform: string | null;
  keyword: string | null;
  depth: number | null;
  status: string;
  error_code: string | null;
  duration_ms: number | null;
};

declare global {
  interface Window {
    electronAPI?: {
      onBackendPort: (callback: (port: string) => void) => unknown;
      removeListener?: (channel: string, wrapper: unknown) => void;
      getBackendPort?: () => Promise<string | null>;
    };
  }
}

export default function App() {
  const [logs, setLogs] = useState<string[]>(['[System] OmniScraper Pro Initialized.']);
  const [isRunning, setIsRunning] = useState(false);
  const [platform, setPlatform] = useState('抖音');
  const [keyword, setKeyword] = useState('Python教程\n自媒体运营');
  const [depth, setDepth] = useState(10);
  
  // AI 模型配置状态
  const [llmModel, setLlmModel] = useState('deepseek-ai/DeepSeek-R1-Distill-Qwen-7B');
  const [llmApiKey, setLlmApiKey] = useState('');
  const [vlmModel, setVlmModel] = useState('deepseek-ai/DeepSeek-V3');
  const [vlmApiKey, setVlmApiKey] = useState('');
  const [llmBaseUrl, setLlmBaseUrl] = useState('https://api.siliconflow.cn/v1');
  const [vlmBaseUrl, setVlmBaseUrl] = useState('https://api.siliconflow.cn/v1');
  
  const [backendHttpBase, setBackendHttpBase] = useState<string>(() => {
    return window.localStorage.getItem('omni.backend_http_base') ?? '';
  });
  const [backendWsUrl, setBackendWsUrl] = useState<string>(() => {
    const saved = window.localStorage.getItem('omni.backend_ws_url');
    if (saved) return saved;
    const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    return `${wsProtocol}://${window.location.host}/ws`;
  });
  const [pipelineTimeoutSeconds, setPipelineTimeoutSeconds] = useState<number>(() => {
    const saved = window.localStorage.getItem('omni.pipeline_timeout_seconds');
    const n = saved ? Number(saved) : 300;
    return Number.isFinite(n) && n > 0 ? n : 300;
  });
  
  // 报告数据状态
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [showReports, setShowReports] = useState(false);
  const [selectedReport, setSelectedReport] = useState<ReportItem | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [reportsError, setReportsError] = useState<string>('');
  const [showDataManagement, setShowDataManagement] = useState(false);
  const [taskRuns, setTaskRuns] = useState<TaskRunItem[]>([]);
  const [taskRunsError, setTaskRunsError] = useState('');
  const [douyinSettingsSummary, setDouyinSettingsSummary] = useState<{
    has_cookies: boolean;
    cookies_count: number;
    user_agent_pool_count: number;
  } | null>(null);
  const [douyinCookiesJson, setDouyinCookiesJson] = useState('');
  const [douyinUserAgentPoolJson, setDouyinUserAgentPoolJson] = useState('');

  const wsRef = useRef<WebSocket | null>(null);
  const logContainerRef = useRef<HTMLDivElement>(null);
  const [isAutoScroll, setIsAutoScroll] = useState(true);
  const reconnectTimerRef = useRef<number | null>(null);
  const reconnectAttemptRef = useRef(0);

  useEffect(() => {
    // 监听 Electron 传来的动态端口
    if (window.electronAPI) {
      const handlePort = (port: string) => {
        if (!port) return;
        setLogs(prev => (prev[prev.length - 1] === `[System] Discovered Backend on port ${port}` ? prev : [...prev, `[System] Discovered Backend on port ${port}`]));
        setBackendHttpBase(`http://127.0.0.1:${port}`);
        setBackendWsUrl(`ws://127.0.0.1:${port}/ws`);
      };
      
      // 主动拉取一次端口，防止竞态条件导致事件丢失
      if (window.electronAPI.getBackendPort) {
        window.electronAPI.getBackendPort().then(handlePort);
      }
      
      window.electronAPI.onBackendPort(handlePort);
      
      // 添加清理函数，防止 React 18 StrictMode 导致事件监听器内存泄漏重复触发
      return () => {
        if (window.electronAPI.removeListener) {
          window.electronAPI.removeListener('backend-port', handlePort);
        }
      };
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem('omni.backend_http_base', backendHttpBase);
    window.localStorage.setItem('omni.backend_ws_url', backendWsUrl);
    window.localStorage.setItem('omni.pipeline_timeout_seconds', String(pipelineTimeoutSeconds));
  }, [backendHttpBase, backendWsUrl, pipelineTimeoutSeconds]);

  const buildApiUrl = useCallback((path: string) => {
    if (!path.startsWith('/')) return path;
    return backendHttpBase ? `${backendHttpBase}${path}` : path;
  }, [backendHttpBase]);

  useEffect(() => {
    const appendLog = (msg: string) => {
      setLogs(prev => (prev[prev.length - 1] === msg ? prev : [...prev, msg]));
    };

    let disposed = false;
    let pingTimer: number | null = null;
    let ws: WebSocket | null = null;

    const clearReconnectTimer = () => {
      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };

    const clearPingTimer = () => {
      if (pingTimer) {
        window.clearInterval(pingTimer);
        pingTimer = null;
      }
    };

    const scheduleReconnect = () => {
      if (disposed) return;
      clearReconnectTimer();
      reconnectAttemptRef.current += 1;
      const delay = Math.min(15000, 800 * reconnectAttemptRef.current);
      reconnectTimerRef.current = window.setTimeout(() => {
        connect();
      }, delay);
    };

    const connect = () => {
      if (disposed) return;
      clearPingTimer();

      try {
        ws = new WebSocket(backendWsUrl);
      } catch {
        appendLog('[Error] Failed to create WebSocket.');
        scheduleReconnect();
        return;
      }

      wsRef.current = ws;

      ws.onopen = () => {
        if (disposed) return;
        reconnectAttemptRef.current = 0;
        appendLog('[System] Connected to Python Engine.');
        clearPingTimer();
        pingTimer = window.setInterval(() => {
          try {
            if (ws && ws.readyState === WebSocket.OPEN) ws.send('ping');
          } catch {
            void 0;
          }
        }, 20000);
      };

      ws.onmessage = (event) => {
        if (disposed) return;
        const raw = String(event.data ?? '');
        let parsed: any = null;
        try {
          parsed = JSON.parse(raw);
        } catch {
          parsed = null;
        }

        let msg = raw;
        if (parsed && typeof parsed === 'object' && typeof parsed.msg === 'string') {
          const level = typeof parsed.level === 'string' ? parsed.level : 'INFO';
          const module = typeof parsed.module === 'string' ? parsed.module : '';
          const reason = typeof parsed.reason === 'string' ? parsed.reason : '';
          const runId = typeof parsed.run_id === 'number' ? parsed.run_id : null;
          msg = `[${level}]${module ? `[${module}]` : ''} ${parsed.msg}${reason ? ` (${reason})` : ''}${runId !== null ? ` [run:${runId}]` : ''}`;
        }

        setLogs(prev => {
          const newLogs = [...prev, msg];
          // 如果日志过多，自动截断前 1000 条，防止 DOM 渲染卡死
          if (newLogs.length > 5000) {
            return newLogs.slice(newLogs.length - 5000);
          }
          return newLogs;
        });
        
        // 识别任务结束标志：无论是完全成功，还是中途报错、没搜到数据、或是正常退出，只要出现以下关键字就解锁按钮
        if (
          msg.includes('任务结束') || 
          msg.includes('任务提前结束') ||
          msg.includes('一键删除任务结果完成') ||
          msg.includes('一键删除任务结果失败')
        ) {
          setIsRunning(false);
        }
      };

      ws.onerror = () => {
        if (disposed) return;
        appendLog('[Error] Failed to connect to Engine.');
      };

      ws.onclose = () => {
        if (disposed) return;
        appendLog('[System] Disconnected.');
        scheduleReconnect();
      };
    };

    connect();

    return () => {
      disposed = true;
      clearReconnectTimer();
      clearPingTimer();
      try {
        ws?.close();
      } catch {
        void 0;
      }
    };
  }, [backendWsUrl]);

  useEffect(() => {
    // 只有当允许自动滚动时，才滚动到底部
    if (isAutoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs, isAutoScroll]);

  const handleScroll = () => {
    if (logContainerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = logContainerRef.current;
      // 如果用户向上滚动了超过 10px，就暂停自动滚动
      const isAtBottom = Math.abs(scrollHeight - clientHeight - scrollTop) < 10;
      setIsAutoScroll(isAtBottom);
    }
  };

  const fetchReports = useCallback(async () => {
    setReportsError('');
    try {
      const primaryUrl = buildApiUrl('/api/reports?limit=20');
      let response: Response | null = null;
      try {
        response = await fetch(primaryUrl);
      } catch {
        response = null;
      }

      if (!response || !response.ok) {
        if (backendHttpBase) {
          response = await fetch('/api/reports?limit=20');
        }
      }

      if (!response || !response.ok) throw new Error('Failed to fetch reports');
      const data = await response.json();
      setReports(data);
      if (Array.isArray(data) && data.length > 0) {
        setSelectedReport(prev => {
          if (!prev) return data[0];
          const found = data.find((r: ReportItem) => r.id === prev.id);
          return found ?? data[0];
        });
      }
    } catch (err) {
      console.error("Failed to fetch reports", err);
      setReportsError(String(err));
    }
  }, [backendHttpBase, buildApiUrl]);

  useEffect(() => {
    if (showReports) {
      fetchReports();
    }
  }, [showReports, fetchReports]);

  const handleStartTask = async () => {
    if (isRunning) return;
    setIsRunning(true);
    setLogs(prev => [...prev, '\n--- Starting New Task ---']);
    
    try {
      const payload = { 
        platform, 
        keyword: keyword.split('\n')[0] || 'Python教程', 
        depth: depth,
        pipeline_timeout_seconds: pipelineTimeoutSeconds,
        llm_model: llmModel,
        llm_api_key: llmApiKey,
        llm_base_url: llmBaseUrl,
        vlm_model: vlmModel,
        vlm_api_key: vlmApiKey,
        vlm_base_url: vlmBaseUrl
      };

      const primaryUrl = buildApiUrl('/api/task/start');
      let response: Response | null = null;
      try {
        response = await fetch(primaryUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      } catch {
        response = null;
      }

      if (!response || !response.ok) {
        if (backendHttpBase) {
          response = await fetch('/api/task/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
        }
      }

      if (!response || !response.ok) throw new Error('Network response was not ok');
      const data = await response.json().catch(() => null);
      if (data && typeof data.run_id === 'number') {
        setLogs(prev => [...prev, `[System] run_id=${data.run_id}`]);
      }
    } catch (err) {
      setLogs(prev => [...prev, `[Error] Failed to trigger task: ${err}`]);
      setIsRunning(false);
    }
  };

  const fetchTaskRuns = useCallback(async () => {
    setTaskRunsError('');
    try {
      const primaryUrl = buildApiUrl('/api/task-runs?limit=20');
      let response: Response | null = null;
      try {
        response = await fetch(primaryUrl);
      } catch {
        response = null;
      }

      if (!response || !response.ok) {
        if (backendHttpBase) response = await fetch('/api/task-runs?limit=20');
      }

      if (!response || !response.ok) throw new Error('Failed to fetch task runs');
      const data = await response.json();
      setTaskRuns(Array.isArray(data) ? data : []);
    } catch (err) {
      setTaskRunsError(String(err));
    }
  }, [backendHttpBase, buildApiUrl]);

  const fetchDouyinSettingsSummary = useCallback(async () => {
    try {
      const primaryUrl = buildApiUrl('/api/settings/douyin');
      let response: Response | null = null;
      try {
        response = await fetch(primaryUrl);
      } catch {
        response = null;
      }

      if (!response || !response.ok) {
        if (backendHttpBase) response = await fetch('/api/settings/douyin');
      }

      if (!response || !response.ok) throw new Error('Failed to fetch douyin settings');
      const data = await response.json();
      setDouyinSettingsSummary(data);
    } catch {
      setDouyinSettingsSummary(null);
    }
  }, [backendHttpBase, buildApiUrl]);

  useEffect(() => {
    if (!showDataManagement) return;
    fetchTaskRuns();
    fetchDouyinSettingsSummary();
  }, [showDataManagement, fetchTaskRuns, fetchDouyinSettingsSummary]);

  const handleClearReports = async () => {
    const ok = window.confirm('确认清空所有报告内容？（保留视频/评论/summary 行）');
    if (!ok) return;
    const url = buildApiUrl('/api/admin/reports/clear');
    await fetch(url, { method: 'POST' }).catch(() => null);
    fetchReports();
  };

  const handleDeleteRun = async (runId: number) => {
    const ok = window.confirm(`确认删除任务批次 run_id=${runId} 的全部结果？（不删除 videos）`);
    if (!ok) return;
    const url = buildApiUrl(`/api/task-runs/${runId}`);
    await fetch(url, { method: 'DELETE' }).catch(() => null);
    fetchTaskRuns();
    fetchReports();
  };

  const handleDeleteAllRuns = async () => {
    const ok = window.confirm('确认一键删除全部任务结果？（分批异步执行）');
    if (!ok) return;
    const url = buildApiUrl('/api/task-runs');
    const res = await fetch(url, { method: 'DELETE' }).catch(() => null);
    const data = await res?.json().catch(() => null);
    if (data && typeof data.task_id === 'string') {
      setLogs(prev => [...prev, `[System] delete_task_id=${data.task_id}`]);
    }
  };

  const handleDeleteVideo = async (videoId: string) => {
    const ok = window.confirm(`确认删除视频 ${videoId} 的全部数据？（全局删除，不可逆）`);
    if (!ok) return;
    const url = buildApiUrl(`/api/videos/${encodeURIComponent(videoId)}`);
    await fetch(url, { method: 'DELETE' }).catch(() => null);
    fetchReports();
    fetchTaskRuns();
  };

  const handleSaveDouyinSettings = async () => {
    let cookies: any = undefined;
    let uaPool: any = undefined;
    try {
      cookies = douyinCookiesJson.trim() ? JSON.parse(douyinCookiesJson) : [];
    } catch {
      setLogs(prev => [...prev, '[Error] Cookies JSON 解析失败']);
      return;
    }
    try {
      uaPool = douyinUserAgentPoolJson.trim() ? JSON.parse(douyinUserAgentPoolJson) : [];
    } catch {
      setLogs(prev => [...prev, '[Error] User-Agent Pool JSON 解析失败']);
      return;
    }

    const url = buildApiUrl('/api/settings/douyin');
    await fetch(url, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cookies, user_agent_pool: uaPool })
    }).catch(() => null);
    fetchDouyinSettingsSummary();
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
            <button 
              onClick={() => setShowReports(true)}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-50 text-indigo-700 rounded-lg hover:bg-indigo-100 transition-colors shadow-sm"
            >
              <FileText className="w-4 h-4" />
              历史报告
            </button>
            <button
              onClick={() => setShowSettings(true)}
              className="flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
            >
              <Settings className="w-4 h-4" />
              全局设置
            </button>
            <button
              onClick={() => setShowDataManagement(true)}
              className="flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
            >
              <Trash2 className="w-4 h-4" />
              数据管理
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

        {showSettings && (
          <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-6 z-50">
            <div className="bg-white rounded-xl shadow-xl border border-gray-100 w-full max-w-2xl">
              <div className="flex items-center justify-between p-6 border-b border-gray-100">
                <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                  <Settings className="w-5 h-5 text-gray-600" />
                  全局设置
                </h2>
                <button
                  onClick={() => setShowSettings(false)}
                  className="p-2 rounded-lg hover:bg-gray-100 text-gray-600"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="p-6 space-y-6">
                <div className="grid grid-cols-2 gap-4">
                  <div className="col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-1">后端 HTTP Base</label>
                    <input
                      className="w-full border border-gray-300 rounded-lg p-2.5"
                      value={backendHttpBase}
                      onChange={(e) => setBackendHttpBase(e.target.value)}
                      placeholder="留空则使用 /api 代理"
                    />
                  </div>
                  <div className="col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-1">后端 WebSocket 地址</label>
                    <input
                      className="w-full border border-gray-300 rounded-lg p-2.5"
                      value={backendWsUrl}
                      onChange={(e) => setBackendWsUrl(e.target.value)}
                      placeholder="例如 ws://127.0.0.1:8000/ws"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">单视频超时 (秒)</label>
                    <input
                      type="number"
                      className="w-full border border-gray-300 rounded-lg p-2.5"
                      value={pipelineTimeoutSeconds}
                      onChange={(e) => setPipelineTimeoutSeconds(Number(e.target.value))}
                      min={30}
                      step={10}
                    />
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between p-6 border-t border-gray-100 bg-gray-50 rounded-b-xl">
                <button
                  onClick={() => {
                    const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
                    setBackendHttpBase('');
                    setBackendWsUrl(`${wsProtocol}://${window.location.host}/ws`);
                    setPipelineTimeoutSeconds(300);
                  }}
                  className="px-4 py-2 rounded-lg bg-white border border-gray-200 text-gray-700 hover:bg-gray-100"
                >
                  恢复默认
                </button>
                <div className="flex gap-3">
                  <button
                    onClick={() => setShowSettings(false)}
                    className="px-4 py-2 rounded-lg bg-white border border-gray-200 text-gray-700 hover:bg-gray-100"
                  >
                    关闭
                  </button>
                  <button
                    onClick={() => setShowSettings(false)}
                    className="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700"
                  >
                    保存
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {showDataManagement && (
          <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-6 z-50">
            <div className="bg-white rounded-xl shadow-xl border border-gray-100 w-full max-w-4xl">
              <div className="flex items-center justify-between p-6 border-b border-gray-100">
                <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                  <Trash2 className="w-5 h-5 text-gray-600" />
                  数据管理
                </h2>
                <button
                  onClick={() => setShowDataManagement(false)}
                  className="p-2 rounded-lg hover:bg-gray-100 text-gray-600"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="p-6 space-y-8 max-h-[80vh] overflow-y-auto">
                <div className="bg-gray-50 border border-gray-200 rounded-xl p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-semibold text-gray-900">清理报告内容</div>
                      <div className="text-xs text-gray-600 mt-1">仅清空报告字段，不删除视频/评论/summary 行</div>
                    </div>
                    <button
                      onClick={handleClearReports}
                      className="px-4 py-2 rounded-lg bg-white border border-gray-200 text-gray-700 hover:bg-gray-100"
                    >
                      清空报告内容
                    </button>
                  </div>
                </div>

                <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-semibold text-gray-900">抖音 Cookie / UA</div>
                      <div className="text-xs text-gray-600 mt-1">
                        {douyinSettingsSummary
                          ? `已设置 Cookie：${douyinSettingsSummary.has_cookies ? '是' : '否'}（${douyinSettingsSummary.cookies_count}） UA 池：${douyinSettingsSummary.user_agent_pool_count}`
                          : '未加载到配置概览'}
                      </div>
                    </div>
                    <button
                      onClick={handleSaveDouyinSettings}
                      className="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700"
                    >
                      保存配置
                    </button>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <div className="text-xs font-medium text-gray-700 mb-1">cookies（JSON 数组）</div>
                      <textarea
                        className="w-full border border-gray-300 rounded-lg p-2.5 font-mono text-xs h-40"
                        value={douyinCookiesJson}
                        onChange={(e) => setDouyinCookiesJson(e.target.value)}
                        placeholder='[{"name":"...","value":"...","domain":".douyin.com","path":"/"}]'
                      />
                    </div>
                    <div>
                      <div className="text-xs font-medium text-gray-700 mb-1">user_agent_pool（JSON 数组）</div>
                      <textarea
                        className="w-full border border-gray-300 rounded-lg p-2.5 font-mono text-xs h-40"
                        value={douyinUserAgentPoolJson}
                        onChange={(e) => setDouyinUserAgentPoolJson(e.target.value)}
                        placeholder='["Mozilla/5.0 ...", "Mozilla/5.0 ..."]'
                      />
                    </div>
                  </div>
                </div>

                <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-semibold text-gray-900">任务批次</div>
                      <div className="text-xs text-gray-600 mt-1">按 run_id 删除该次任务产出（不删除 videos）</div>
                    </div>
                    <div className="flex gap-3">
                      <button
                        onClick={fetchTaskRuns}
                        className="px-4 py-2 rounded-lg bg-white border border-gray-200 text-gray-700 hover:bg-gray-100"
                      >
                        刷新
                      </button>
                      <button
                        onClick={handleDeleteAllRuns}
                        className="px-4 py-2 rounded-lg bg-white border border-gray-200 text-gray-700 hover:bg-gray-100"
                      >
                        一键删除全部任务结果
                      </button>
                    </div>
                  </div>

                  {taskRunsError && <div className="text-xs text-red-600">{taskRunsError}</div>}

                  <div className="border border-gray-200 rounded-lg overflow-hidden bg-white">
                    <div className="grid grid-cols-6 gap-2 px-3 py-2 text-xs font-semibold text-gray-600 bg-gray-100">
                      <div>run_id</div>
                      <div className="col-span-2">关键词</div>
                      <div>状态</div>
                      <div>耗时</div>
                      <div />
                    </div>
                    <div className="max-h-64 overflow-y-auto">
                      {taskRuns.length === 0 ? (
                        <div className="text-xs text-gray-500 p-3">暂无任务批次</div>
                      ) : (
                        taskRuns.map((r) => (
                          <div key={r.id} className="grid grid-cols-6 gap-2 px-3 py-2 text-xs border-t border-gray-100 items-center">
                            <div className="font-mono">{r.id}</div>
                            <div className="col-span-2 truncate">{r.keyword ?? ''}</div>
                            <div className="truncate">{r.status}{r.error_code ? `(${r.error_code})` : ''}</div>
                            <div className="truncate">{typeof r.duration_ms === 'number' ? `${Math.round(r.duration_ms / 1000)}s` : ''}</div>
                            <div className="flex justify-end">
                              <button
                                onClick={() => handleDeleteRun(r.id)}
                                className="px-2 py-1 rounded bg-white border border-gray-200 hover:bg-gray-100 text-gray-700"
                              >
                                删除
                              </button>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-end p-6 border-t border-gray-100 bg-gray-50 rounded-b-xl">
                <button
                  onClick={() => setShowDataManagement(false)}
                  className="px-4 py-2 rounded-lg bg-white border border-gray-200 text-gray-700 hover:bg-gray-100"
                >
                  关闭
                </button>
              </div>
            </div>
          </div>
        )}

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
                    value={keyword}
                    onChange={e => setKeyword(e.target.value)}
                  />
                </div>
                
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">视频采集数量</label>
                    <input type="number" value={depth} onChange={e => setDepth(Number(e.target.value))} className="w-full border border-gray-300 rounded-lg p-2.5" />
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
            
            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Bot className="w-5 h-5 text-indigo-500" />
                AI 模型与密钥配置
              </h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">LLM 文本模型 (总结与分析)</label>
                  <input 
                    list="llm-models"
                    className="w-full border border-gray-300 rounded-lg p-2.5 mb-2 bg-white text-sm"
                    value={llmModel}
                    onChange={(e) => setLlmModel(e.target.value)}
                    placeholder="选择或输入模型名称，例如: deepseek-chat"
                  />
                  <datalist id="llm-models">
                    <option value="deepseek-chat">DeepSeek Chat (V3 官方)</option>
                    <option value="deepseek-reasoner">DeepSeek Reasoner (R1 官方)</option>
                    <option value="deepseek-ai/DeepSeek-V3">DeepSeek V3 (SiliconFlow 硅基流动)</option>
                    <option value="deepseek-ai/DeepSeek-R1">DeepSeek R1 (SiliconFlow 硅基流动)</option>
                    <option value="qwen-plus">Qwen Plus (阿里云百炼)</option>
                    <option value="qwen-max">Qwen Max (阿里云百炼)</option>
                    <option value="glm-4-plus">GLM-4-Plus (智谱)</option>
                    <option value="moonshot-v1-8k">Moonshot (Kimi)</option>
                    <option value="gpt-4o">GPT-4o (OpenAI)</option>
                    <option value="claude-3-5-sonnet-20241022">Claude 3.5 Sonnet</option>
                  </datalist>
                  <div className="grid grid-cols-2 gap-2 mb-2">
                    <input 
                      type="text" 
                      placeholder="Base URL (例: https://api.deepseek.com/v1 或 https://api.siliconflow.cn/v1)" 
                      value={llmBaseUrl}
                      onChange={(e) => setLlmBaseUrl(e.target.value)}
                      className="w-full border border-gray-300 rounded-lg p-2 font-mono text-xs text-gray-600" 
                    />
                    <input 
                      type="password" 
                      placeholder="API Key (为空用系统配置)" 
                      value={llmApiKey}
                      onChange={(e) => setLlmApiKey(e.target.value)}
                      className="w-full border border-gray-300 rounded-lg p-2 font-mono text-xs text-gray-600" 
                    />
                  </div>
                </div>
                
                <div className="pt-3 border-t border-gray-100">
                  <label className="block text-sm font-medium text-gray-700 mb-1">VLM 多模态模型 (OCR/画面理解)</label>
                  <input 
                    list="vlm-models"
                    className="w-full border border-gray-300 rounded-lg p-2.5 mb-2 bg-white text-sm"
                    value={vlmModel}
                    onChange={(e) => setVlmModel(e.target.value)}
                    placeholder="选择或输入视觉模型，例如: gpt-4o"
                  />
                  <datalist id="vlm-models">
                    <option value="Pro/OpenGVLab/InternVL2.5-78B">InternVL 2.5 78B (SiliconFlow 硅基流动)</option>
                    <option value="OpenGVLab/InternVL2-26B">InternVL 2 26B (SiliconFlow 硅基流动)</option>
                    <option value="qwen-vl-plus">Qwen VL Plus (阿里云百炼)</option>
                    <option value="qwen-vl-max">Qwen VL Max (阿里云百炼)</option>
                    <option value="glm-4v-plus">GLM-4V-Plus (智谱)</option>
                    <option value="gpt-4o">GPT-4o (Vision)</option>
                    <option value="claude-3-5-sonnet-20241022">Claude 3.5 Sonnet (Vision)</option>
                  </datalist>
                  <div className="grid grid-cols-2 gap-2">
                    <input 
                      type="text" 
                      placeholder="Base URL (例: https://api.siliconflow.cn/v1)" 
                      value={vlmBaseUrl}
                      onChange={(e) => setVlmBaseUrl(e.target.value)}
                      className="w-full border border-gray-300 rounded-lg p-2 font-mono text-xs text-gray-600" 
                    />
                    <input 
                      type="password" 
                      placeholder="API Key" 
                      value={vlmApiKey}
                      onChange={(e) => setVlmApiKey(e.target.value)}
                      className="w-full border border-gray-300 rounded-lg p-2 font-mono text-xs text-gray-600" 
                    />
                  </div>
                </div>
              </div>
            </div>
            
            <div className="bg-gray-900 p-6 rounded-xl shadow-sm border border-gray-800 text-gray-300 h-64 flex flex-col relative">
              <h2 className="text-lg font-semibold mb-4 flex items-center justify-between text-white shrink-0">
                <div className="flex items-center gap-2">
                  <Terminal className="w-5 h-5 text-green-400" />
                  执行日志 (Console)
                </div>
                {!isAutoScroll && (
                  <button 
                    onClick={() => setIsAutoScroll(true)}
                    className="text-xs bg-gray-700 hover:bg-gray-600 px-2 py-1 rounded text-gray-300"
                  >
                    返回底部
                  </button>
                )}
              </h2>
              <div 
                ref={logContainerRef}
                onScroll={handleScroll}
                className="flex-1 overflow-y-auto font-mono text-sm space-y-1 p-2 bg-black/50 rounded border border-gray-700 scroll-smooth"
              >
                {logs.map((log, i) => (
                  <div key={i} className={`${log.includes('[Error]') ? 'text-red-400' : log.includes('[SUCCESS]') ? 'text-green-400' : 'text-gray-300'}`}>
                    {log}
                  </div>
                ))}
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

      {showReports && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-6">
          <div className="bg-white w-full max-w-5xl h-[85vh] rounded-2xl shadow-2xl flex overflow-hidden border border-gray-200 animate-in fade-in zoom-in duration-200">
            <div className="w-1/3 bg-gray-50 border-r border-gray-200 flex flex-col h-full">
              <div className="p-4 border-b border-gray-200 bg-white flex items-center justify-between">
                <h3 className="font-semibold text-gray-800 flex items-center gap-2">
                  <Database className="w-4 h-4 text-blue-500" /> 
                  分析报告库 ({reports.length})
                </h3>
                <button onClick={() => setShowReports(false)} className="p-1 hover:bg-gray-100 rounded text-gray-500">
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="flex-1 overflow-y-auto p-3 space-y-2">
                {reports.length === 0 ? (
                  <div className="text-sm text-gray-500 text-center mt-10">
                    {reportsError ? `报告拉取失败：${reportsError}` : '暂无生成的分析报告'}
                  </div>
                ) : (
                  reports.map(r => (
                    <button
                      key={r.id}
                      onClick={() => setSelectedReport(r)}
                      className={`w-full text-left p-3 rounded-lg border transition-all ${selectedReport?.id === r.id ? 'bg-blue-50 border-blue-200 shadow-sm' : 'bg-white border-gray-100 hover:border-blue-100 hover:bg-gray-50'}`}
                    >
                      <div className="text-xs text-gray-400 mb-1 flex justify-between">
                        <span>Video ID: {r.video_id}</span>
                        <span>#{r.id}</span>
                      </div>
                      <div className="text-sm font-medium text-gray-800 line-clamp-2">
                        {r.markdown.split('\n')[0].replace(/#+\s*/, '') || '无标题报告'}
                      </div>
                    </button>
                  ))
                )}
              </div>
            </div>
            
            <div className="w-2/3 bg-white h-full flex flex-col">
              <div className="p-4 border-b border-gray-100 bg-white flex justify-between items-center shadow-sm z-10">
                <h3 className="font-semibold text-gray-800 flex items-center gap-2">
                  <FileText className="w-4 h-4 text-green-500" />
                  Markdown 报告预览
                </h3>
                {selectedReport && (
                  <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded font-medium">已入库</span>
                )}
              </div>
              <div className="flex-1 overflow-y-auto p-8 bg-gray-50/50 prose prose-sm max-w-none prose-headings:text-gray-800 prose-a:text-blue-600 prose-code:text-pink-600 prose-code:bg-pink-50 prose-code:px-1 prose-code:rounded">
                {selectedReport ? (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {selectedReport.markdown}
                  </ReactMarkdown>
                ) : (
                  <div className="h-full flex items-center justify-center text-gray-400">
                    请在左侧选择一份报告进行预览
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
