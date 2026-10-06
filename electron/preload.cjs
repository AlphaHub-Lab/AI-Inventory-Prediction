const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('stockwiseDesktop', Object.freeze({
  getApiBaseUrl: () => ipcRenderer.invoke('desktop:get-api-base-url'),
}))
