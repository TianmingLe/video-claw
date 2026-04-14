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
    cwd: path.join(__dirname, '..', '..'), // 确保在 workspace 根目录运行
    env: { ...process.env, PYTHONUNBUFFERED: '1' }
  });

  pythonProcess.stdout.on('data', (data) => {
    const output = data.toString();
    console.log(`[Python] ${output}`);
    
    // 解析 Python 后端分配的端口
    const portMatch = output.match(/Starting server on port (\d+)/);
    if (portMatch && mainWindow) {
      const port = portMatch[1];
      // 通过 webContents 将端口号发送给前端 React
      mainWindow.webContents.send('backend-port', port);
    }
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
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
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