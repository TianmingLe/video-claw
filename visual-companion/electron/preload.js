const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  getBackendPort: () => ipcRenderer.invoke('get-backend-port'),
  onBackendPort: (callback) => {
    // Keep a reference to the wrapper so we can remove it later
    const wrapper = (_event, port) => callback(port);
    ipcRenderer.on('backend-port', wrapper);
    return wrapper;
  },
  removeListener: (channel, wrapper) => {
    ipcRenderer.removeListener(channel, wrapper);
  }
});