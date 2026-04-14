const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  onBackendPort: (callback) => ipcRenderer.on('backend-port', (_event, port) => callback(port))
});