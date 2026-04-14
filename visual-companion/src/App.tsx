import { useState, useEffect, useRef } from 'react';
import {
  Search, Settings, Play, Database, BarChart, Terminal, Download, Bot, ShieldAlert
} from 'lucide-react';

// 扩展全局 Window 接口以支持 TypeScript 编译
declare global {
  interface Window {
    electronAPI: any;
  }
}

export default function App() {
  const [logs, setLogs] = useState<string[]>(['[System] OmniScraper Pro Initialized.']);
  const [isRunning, setIsRunning] = useState(false);
  const [platform, setPlatform] = useState('抖音');
  const [keyword, setKeyword] = useState('Python教程\n自媒体运营');
  const [depth, setDepth] = useState(10);
  
  // AI 模型配置状态
  const [llmModel, setLlmModel] = useState('gpt-4o-mini');
  const [llmApiKey, setLlmApiKey] = useState('');
  const [vlmModel, setVlmModel] = useState('gpt-4o');
  const [vlmApiKey, setVlmApiKey] = useState('');
  
  const [backendPort, setBackendPort] = useState<string>('8000'); // 默认回退
  const wsRef = useRef<WebSocket | null>(null);
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // 监听 Electron 传来的动态端口
    if (window.electronAPI) {
      window.electronAPI.onBackendPort((port: string) => {
        setLogs(prev => [...prev, `[System] Discovered Backend on port ${port}`]);
        setBackendPort(port);
      });
    }
  }, []);

  useEffect(() => {
    // 根据当前已知的 backendPort 连接 WebSocket
    const ws = new WebSocket(`ws://127.0.0.1:${backendPort}/ws`);
    ws.onopen = () => setLogs(prev => [...prev, `[System] Connected to Python Engine on :${backendPort}.`]);
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
  }, [backendPort]);

  useEffect(() => {
    // 自动滚动到最新日志
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const handleStartTask = async () => {
    if (isRunning) return;
    setIsRunning(true);
    setLogs(prev => [...prev, '\n--- Starting New Task ---']);
    
    try {
      const response = await fetch(`http://127.0.0.1:${backendPort}/api/task/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          platform, 
          keyword: keyword.split('\n')[0] || 'Python教程', 
          depth: depth,
          llm_model: llmModel,
          llm_api_key: llmApiKey,
          vlm_model: vlmModel,
          vlm_api_key: vlmApiKey
        })
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
                  <label className="block text-sm font-medium text-gray-700 mb-1">LLM 文本模型 (用于总结与分析)</label>
                  <select 
                    className="w-full border border-gray-300 rounded-lg p-2.5 mb-2 bg-white"
                    value={llmModel}
                    onChange={(e) => setLlmModel(e.target.value)}
                  >
                    <option value="gpt-4o-mini">GPT-4o Mini (推荐)</option>
                    <option value="gpt-4o">GPT-4o</option>
                    <option value="claude-3-5-sonnet-20240620">Claude 3.5 Sonnet</option>
                    <option value="deepseek-chat">DeepSeek Chat</option>
                    <option value="custom">自定义模型</option>
                  </select>
                  <input 
                    type="password" 
                    placeholder="输入 LLM API Key (为空则使用环境配置或 Fake 模式)" 
                    value={llmApiKey}
                    onChange={(e) => setLlmApiKey(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg p-2.5 font-mono text-sm" 
                  />
                </div>
                
                <div className="pt-2 border-t border-gray-100">
                  <label className="block text-sm font-medium text-gray-700 mb-1">VLM 多模态模型 (用于 OCR/画面理解)</label>
                  <select 
                    className="w-full border border-gray-300 rounded-lg p-2.5 mb-2 bg-white"
                    value={vlmModel}
                    onChange={(e) => setVlmModel(e.target.value)}
                  >
                    <option value="gpt-4o">GPT-4o (Vision)</option>
                    <option value="claude-3-5-sonnet-20240620">Claude 3.5 Sonnet</option>
                    <option value="custom">自定义模型</option>
                  </select>
                  <input 
                    type="password" 
                    placeholder="输入 VLM API Key (为空则使用环境配置或 Fake 模式)" 
                    value={vlmApiKey}
                    onChange={(e) => setVlmApiKey(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg p-2.5 font-mono text-sm" 
                  />
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