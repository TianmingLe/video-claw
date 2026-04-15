const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const isDev = require('electron-is-dev');
const { spawn } = require('child_process');

let mainWindow;
let pythonProcess = null;
let backendPort = null;

function startPythonBackend() {
  // Determine correct paths based on whether app is packaged (.asar)
  // In dev, __dirname is visual-companion/electron
  // In prod, __dirname is visual-companion/resources/app.asar/electron (or similar)
  const isPackaged = app.isPackaged;
  
  let cwdPath;
  let scriptPath;
  
  if (isPackaged) {
    // When packaged, backend should ideally be placed outside the asar 
    // or bundled as an executable. Assuming it's placed next to the executable in a 'backend' folder
    cwdPath = path.join(process.resourcesPath, '..');
    scriptPath = path.join(cwdPath, 'backend', 'main.py');
  } else {
    cwdPath = path.join(__dirname, '..', '..');
    scriptPath = path.join(cwdPath, 'backend', 'main.py');
  }
  
  const pythonPath = 'python';
  
  pythonProcess = spawn(pythonPath, [scriptPath], {
    cwd: cwdPath,
    env: { ...process.env, PYTHONUNBUFFERED: '1' }
  });

  pythonProcess.stdout.on('data', (data) => {
    const output = data.toString();
    console.log(`[Python] ${output}`);
    
    // 解析 Python 后端分配的端口
    const portMatch = output.match(/Starting server on port (\d+)/);
    if (portMatch) {
      backendPort = portMatch[1];
      if (mainWindow) {
        // 尝试主动推送给前端
        mainWindow.webContents.send('backend-port', backendPort);
      }
    }
  });

  pythonProcess.stderr.on('data', (data) => {
    console.error(`[Python Err] ${data.toString()}`);
  });

  pythonProcess.on('close', (code) => {
    console.log(`Python process exited with code ${code}`);
  });
}

// 允许前端主动拉取端口，解决启动竞态问题（React 还没挂载完 Python 就发了端口）
ipcMain.handle('get-backend-port', () => {
  return backendPort;
});

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