import React from 'react';
import { 
  Search, 
  Settings, 
  Play, 
  Clock, 
  FileJson, 
  FileSpreadsheet, 
  Database,
  BarChart,
  Terminal,
  Download,
  MessageSquare,
  Bot,
  ShieldAlert,
  Video
} from 'lucide-react';

export default function App() {
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
            <button className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors shadow-sm">
              <Play className="w-4 h-4" />
              新建任务
            </button>
          </div>
        </header>

        <div className="grid grid-cols-3 gap-6">
          {/* 左侧：任务配置 */}
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
                    {['抖音', '小红书', 'Bilibili', 'YouTube', '快手'].map(platform => (
                      <label key={platform} className="flex items-center gap-2 p-2 border rounded-lg cursor-pointer hover:bg-gray-50">
                        <input type="radio" name="platform" defaultChecked={platform === '抖音'} className="text-blue-600" />
                        <span className="text-sm">{platform}</span>
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
                    <label className="block text-sm font-medium text-gray-700 mb-1">视频采集数量 (Top N)</label>
                    <input type="number" defaultValue={100} className="w-full border border-gray-300 rounded-lg p-2.5" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">一级评论深度</label>
                    <input type="number" defaultValue={200} className="w-full border border-gray-300 rounded-lg p-2.5" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">每条回复深度</label>
                    <input type="number" defaultValue={20} className="w-full border border-gray-300 rounded-lg p-2.5" />
                  </div>
                </div>
                <p className="text-xs text-gray-500 mt-1">注：设置过大的采集深度会成倍增加耗时，系统会自动在请求间加入随机延迟以避免触发平台风控。</p>
              </div>
            </div>

            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Bot className="w-5 h-5 text-purple-500" />
                AI 分析与多模态配置
              </h2>
              
              <div className="space-y-4">
                <div className="p-4 bg-purple-50 rounded-lg border border-purple-100">
                  <h3 className="font-medium text-purple-900 mb-2">文本价值判定与总结 (LLM)</h3>
                  <div className="flex gap-4 mb-3">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input type="radio" name="llm" className="text-purple-600" defaultChecked />
                      <span className="text-sm">OpenAI 兼容接口</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer opacity-50">
                      <input type="radio" name="llm" className="text-purple-600" disabled />
                      <span className="text-sm">OpenClaw 预留</span>
                    </label>
                  </div>
                  <input 
                    type="text" 
                    className="w-full border border-gray-300 rounded-md p-2 text-sm mb-2"
                    placeholder="API Base URL (e.g. https://api.openai.com/v1)"
                  />
                  <input 
                    type="password" 
                    className="w-full border border-gray-300 rounded-md p-2 text-sm"
                    placeholder="API Key"
                  />
                </div>

                <div className="p-4 bg-blue-50 rounded-lg border border-blue-100">
                  <h3 className="font-medium text-blue-900 mb-2">视频内容解析策略</h3>
                  <div className="space-y-3">
                    <label className="flex items-center gap-2">
                      <input type="checkbox" className="text-blue-600 rounded" defaultChecked />
                      <span className="text-sm font-medium">音频转文本 (ASR)</span>
                      <span className="text-xs text-gray-500 ml-2">- 提取视频旁白/对话</span>
                    </label>
                    <label className="flex items-center gap-2">
                      <input type="checkbox" className="text-blue-600 rounded" defaultChecked />
                      <span className="text-sm font-medium">画面文字提取 (OCR)</span>
                      <span className="text-xs text-gray-500 ml-2">- 识别视频画面中的字幕或PPT文字</span>
                    </label>
                    <div className="pt-2 border-t border-blue-200">
                      <label className="flex items-center gap-2">
                        <input type="checkbox" className="text-blue-600 rounded" />
                        <span className="text-sm font-medium text-blue-800 flex items-center gap-1">
                          <Video className="w-4 h-4" /> 视频多模态理解大模型 (VLM)
                        </span>
                        <span className="text-xs bg-blue-200 text-blue-800 px-1.5 rounded ml-2">Beta</span>
                      </label>
                      <p className="text-xs text-gray-500 ml-6 mt-1">
                        (预留接口) 接入如 GPT-4V/Gemini/Qwen-VL 等多模态模型，让 AI 直接"看懂"视频画面动作与场景。当前暂不处理，留作二次开发。
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* 右侧：输出与状态 */}
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
                    <div className="text-xs text-gray-500">结构化存储，支持关联查询</div>
                  </div>
                  <input type="checkbox" defaultChecked className="text-blue-600 rounded" />
                </label>
                <label className="flex items-center gap-3 p-3 border rounded-lg hover:bg-gray-50 cursor-pointer">
                  <FileSpreadsheet className="w-5 h-5 text-green-600" />
                  <div className="flex-1">
                    <div className="font-medium text-sm">Excel/CSV 导出</div>
                    <div className="text-xs text-gray-500">便于人工阅读和二次处理</div>
                  </div>
                  <input type="checkbox" defaultChecked className="text-blue-600 rounded" />
                </label>
                <label className="flex items-center gap-3 p-3 border rounded-lg hover:bg-gray-50 cursor-pointer">
                  <FileJson className="w-5 h-5 text-yellow-600" />
                  <div className="flex-1">
                    <div className="font-medium text-sm">JSON 序列化</div>
                    <div className="text-xs text-gray-500">完整嵌套对话数据</div>
                  </div>
                  <input type="checkbox" defaultChecked className="text-blue-600 rounded" />
                </label>
                <label className="flex items-center gap-3 p-3 border rounded-lg hover:bg-gray-50 cursor-pointer border-blue-200 bg-blue-50">
                  <BarChart className="w-5 h-5 text-blue-600" />
                  <div className="flex-1">
                    <div className="font-medium text-sm">Markdown 分析报告</div>
                    <div className="text-xs text-gray-500">包含 AI 总结的干货输出</div>
                  </div>
                  <input type="checkbox" defaultChecked className="text-blue-600 rounded" />
                </label>
              </div>
            </div>

            <div className="bg-gray-900 p-6 rounded-xl shadow-sm border border-gray-800 text-gray-300">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2 text-white">
                <Terminal className="w-5 h-5 text-gray-400" />
                运行方式
              </h2>
              <div className="space-y-3 text-sm">
                <div className="flex items-center justify-between p-2 hover:bg-gray-800 rounded">
                  <span>Web 面板执行</span>
                  <span className="text-green-400">● 活跃</span>
                </div>
                <div className="flex items-center justify-between p-2 hover:bg-gray-800 rounded">
                  <span>CLI 命令行</span>
                  <span className="text-gray-500">待命</span>
                </div>
                <div className="flex items-center justify-between p-2 hover:bg-gray-800 rounded">
                  <span className="flex items-center gap-2">
                    <Clock className="w-4 h-4" /> 定时任务 (Cron)
                  </span>
                  <button className="text-blue-400 hover:text-blue-300 text-xs border border-blue-400/30 px-2 py-1 rounded">配置</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}