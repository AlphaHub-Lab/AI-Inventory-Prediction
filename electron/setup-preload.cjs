const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('stockwiseDesktop', Object.freeze({
  saveDatabaseUrl: (value) => ipcRenderer.invoke('desktop:save-database-url', value),
}))
