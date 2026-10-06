const { app, BrowserWindow, dialog, ipcMain, Menu, shell, safeStorage } = require('electron')
const { autoUpdater } = require('electron-updater')
const { spawn } = require('node:child_process')
const { randomBytes } = require('node:crypto')
const fs = require('node:fs')
const http = require('node:http')
const net = require('node:net')
const path = require('node:path')

const APP_NAME = 'Stockwise AI'
const MAX_LOG_BYTES = 5 * 1024 * 1024
app.setName(APP_NAME)
if (process.platform === 'win32') app.setAppUserModelId('com.stockwise.inventory')

let mainWindow
let setupWindow
let backendProcess
let backendPort
let backendShutdownToken
let backendStopPromise
let isQuitting = false
let isStoppingBackend = false

const userData = app.getPath('userData')
const configPath = path.join(userData, 'connection.enc')
const logPath = path.join(userData, 'logs', 'desktop.log')

function writeLog(level, message) {
  const line = `${new Date().toISOString()} [${level}] ${message}\n`
  try {
    fs.mkdirSync(path.dirname(logPath), { recursive: true })
    if (fs.existsSync(logPath) && fs.statSync(logPath).size > MAX_LOG_BYTES) {
      fs.renameSync(logPath, `${logPath}.1`)
    }
    fs.appendFileSync(logPath, line, { encoding: 'utf8' })
  } catch { /* Logging must not prevent startup. */ }
}

function readConfiguration() {
  if (!fs.existsSync(configPath)) return null
  if (!safeStorage.isEncryptionAvailable()) throw new Error('The operating system credential store is unavailable. Unlock your desktop session and restart Stockwise AI.')
  const encrypted = fs.readFileSync(configPath)
  return JSON.parse(safeStorage.decryptString(encrypted))
}

function saveConfiguration(databaseUrl) {
  const value = String(databaseUrl || '').trim()
  if (value.length > 4096) throw new Error('The PostgreSQL URL is too long.')
  if (!/^postgresql(?:\+psycopg)?:\/\//i.test(value)) throw new Error('Enter a PostgreSQL URL beginning with postgresql:// or postgresql+psycopg://.')
  let parsed
  try { parsed = new URL(value) } catch { throw new Error('The PostgreSQL URL is not valid.') }
  if (!parsed.hostname || !parsed.username || !parsed.password) throw new Error('The PostgreSQL URL must include a host, username, and password.')
  const localHosts = new Set(['localhost', '127.0.0.1', '[::1]'])
  const sslmode = parsed.searchParams.get('sslmode')
  if (!localHosts.has(parsed.hostname.toLowerCase()) && !['require', 'verify-ca', 'verify-full'].includes(sslmode)) {
    throw new Error('Remote PostgreSQL connections must set sslmode=require or a stronger TLS mode.')
  }
  if (!safeStorage.isEncryptionAvailable()) throw new Error('The operating system credential store is unavailable. Unlock your desktop session and restart Stockwise AI.')
  fs.mkdirSync(userData, { recursive: true })
  const current = fs.existsSync(configPath) ? readConfiguration() : {}
  const config = {
    databaseUrl: value,
    secretKey: current.secretKey || randomBytes(48).toString('hex'),
  }
  const encrypted = safeStorage.encryptString(JSON.stringify(config))
  fs.writeFileSync(configPath, encrypted, { mode: 0o600 })
  return config
}

function reserveLoopbackPort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer()
    server.once('error', reject)
    server.listen(0, '127.0.0.1', () => {
      const address = server.address()
      const port = typeof address === 'object' && address ? address.port : 0
      server.close(error => error ? reject(error) : resolve(port))
    })
  })
}

function backendCommand() {
  const executable = path.join(process.resourcesPath, 'backend', `stockwise-backend${process.platform === 'win32' ? '.exe' : ''}`)
  if (app.isPackaged) {
    if (!fs.existsSync(executable)) throw new Error(`The packaged API service is missing: ${executable}`)
    return { command: executable, args: ['--host', '127.0.0.1', '--port', String(backendPort)] }
  }
  const python = process.platform === 'win32'
    ? (fs.existsSync(path.join(app.getAppPath(), '.venv', 'Scripts', 'python.exe')) ? path.join(app.getAppPath(), '.venv', 'Scripts', 'python.exe') : 'python')
    : (fs.existsSync(path.join(app.getAppPath(), '.venv', 'bin', 'python')) ? path.join(app.getAppPath(), '.venv', 'bin', 'python') : 'python3')
  return { command: python, args: [path.join(cwdForBackend(), 'desktop_server.py'), '--host', '127.0.0.1', '--port', String(backendPort)] }
}

function cwdForBackend() {
  return path.join(app.getAppPath(), 'backend')
}

async function waitForBackend(timeoutMs = 45000) {
  const endpoint = `http://127.0.0.1:${backendPort}/health`
  const deadline = Date.now() + timeoutMs
  let lastError = 'The API service did not become ready.'
  while (Date.now() < deadline) {
    if (!backendProcess || backendProcess.exitCode !== null) throw new Error(lastError)
    try {
      const ready = await new Promise((resolve, reject) => {
        const request = http.get(endpoint, response => {
          let data = ''
          response.setEncoding('utf8')
          response.on('data', chunk => { data += chunk })
          response.on('end', () => response.statusCode === 200 ? resolve(data) : reject(new Error(`API health check returned ${response.statusCode}.`)))
        })
        request.setTimeout(1200, () => request.destroy(new Error('Health check timed out.')))
        request.once('error', reject)
      })
      return ready
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error)
      await new Promise(resolve => setTimeout(resolve, 500))
    }
  }
  throw new Error(`The API did not connect to PostgreSQL. Check that the database is reachable and that its schema is initialized. ${lastError}`)
}

function stopBackend() {
  const child = backendProcess
  if (!child || child.exitCode !== null) return Promise.resolve()
  if (backendStopPromise) return backendStopPromise
  isStoppingBackend = true
  backendStopPromise = new Promise(resolve => {
    let finished = false
    const finish = () => {
      if (finished) return
      finished = true
      clearTimeout(timer)
      if (backendProcess === child) backendShutdownToken = undefined
      resolve()
      backendStopPromise = undefined
      isStoppingBackend = false
    }
    const timer = setTimeout(() => {
      writeLog('warn', 'API service did not stop cleanly; terminating it.')
      child.kill()
      finish()
    }, 5000)
    child.once('exit', finish)
    const request = http.request({
      hostname: '127.0.0.1',
      port: backendPort,
      path: '/desktop/shutdown',
      method: 'POST',
      headers: { 'X-Desktop-Shutdown-Token': backendShutdownToken || '' },
    }, response => response.resume())
    request.setTimeout(1500, () => request.destroy(new Error('Shutdown request timed out.')))
    request.once('error', error => {
      writeLog('warn', `Graceful API shutdown was unavailable: ${error.message}`)
      child.kill()
      finish()
    })
    request.end()
  })
  return backendStopPromise
}

async function startBackend(configuration) {
  backendPort = await reserveLoopbackPort()
  const cwd = app.isPackaged ? process.resourcesPath : path.join(app.getAppPath(), 'backend')
  const inheritedKeys = ['PATH', 'SystemRoot', 'WINDIR', 'TEMP', 'TMP', 'HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'LD_LIBRARY_PATH', 'DYLD_LIBRARY_PATH']
  const env = Object.fromEntries(inheritedKeys.filter(key => process.env[key]).map(key => [key, process.env[key]]))
  const modelDirectory = path.join(userData, 'models')
  fs.mkdirSync(modelDirectory, { recursive: true })
  backendShutdownToken = randomBytes(32).toString('hex')
  backendStopPromise = undefined
  Object.assign(env, {
    DATABASE_URL: configuration.databaseUrl,
    SECRET_KEY: configuration.secretKey,
    ENVIRONMENT: 'production',
    CORS_ORIGINS: app.isPackaged ? 'null' : 'null,http://localhost:5173,http://127.0.0.1:5173',
    STOCKWISE_MODEL_DIR: modelDirectory,
    DESKTOP_SHUTDOWN_TOKEN: backendShutdownToken,
    PYTHONUNBUFFERED: '1',
  })
  if (!app.isPackaged) env.PYTHONPATH = cwd
  const { command, args } = backendCommand()
  writeLog('info', 'Starting the local API service on loopback.')
  backendProcess = spawn(command, args, { cwd, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] })
  backendProcess.stdout.on('data', chunk => writeLog('api', String(chunk).trimEnd()))
  backendProcess.stderr.on('data', chunk => writeLog('api', String(chunk).trimEnd()))
  backendProcess.once('error', error => writeLog('error', `Could not start API service: ${error.message}`))
  backendProcess.once('exit', (code, signal) => {
    writeLog('warn', `API service stopped (code ${code}, signal ${signal}).`)
    if (!isQuitting && !isStoppingBackend && mainWindow && !mainWindow.isDestroyed()) {
      dialog.showMessageBox(mainWindow, { type: 'error', title: APP_NAME, message: 'The local API service stopped.', detail: 'Restart Stockwise AI. If the issue continues, check the desktop log in the application data folder.' })
        .finally(() => app.quit())
    }
  })
  await waitForBackend()
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 1100,
    minHeight: 700,
    show: false,
    title: APP_NAME,
    backgroundColor: '#0b1220',
    icon: path.join(app.getAppPath(), 'assets', 'icons', 'stockwise.png'),
    webPreferences: {
      preload: path.join(app.getAppPath(), 'electron', 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
    },
  })
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    try {
      const target = new URL(url)
      if (target.protocol === 'https:' || target.protocol === 'http:') void shell.openExternal(target.href)
    } catch { writeLog('warn', 'Blocked an invalid external URL.') }
    return { action: 'deny' }
  })
  mainWindow.webContents.on('will-navigate', (event, url) => {
    let allowed = false
    try {
      allowed = !app.isPackaged && process.env.VITE_DEV_SERVER_URL && new URL(url).origin === new URL(process.env.VITE_DEV_SERVER_URL).origin
    } catch { /* Invalid URLs are handled below. */ }
    if (allowed) return
    event.preventDefault()
    try {
      const target = new URL(url)
      if (target.protocol === 'https:' || target.protocol === 'http:') void shell.openExternal(target.href)
    } catch { writeLog('warn', 'Blocked an invalid navigation URL.') }
  })
  mainWindow.webContents.on('render-process-gone', (_event, details) => {
    writeLog('error', `Renderer process exited: ${details.reason}.`)
  })
  mainWindow.once('ready-to-show', () => mainWindow.show())
  mainWindow.on('closed', () => { mainWindow = undefined })
  if (!app.isPackaged && process.env.VITE_DEV_SERVER_URL) void mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL)
  else void mainWindow.loadFile(path.join(app.getAppPath(), 'frontend', 'dist', 'index.html'))
}

function createSetupWindow(initialMessage = '') {
  setupWindow = new BrowserWindow({
    width: 640,
    height: 620,
    resizable: false,
    title: `Connect ${APP_NAME}`,
    backgroundColor: '#0b1220',
    webPreferences: {
      preload: path.join(app.getAppPath(), 'electron', 'setup-preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })
  setupWindow.loadFile(path.join(app.getAppPath(), 'electron', 'setup.html'), { query: initialMessage ? { error: initialMessage } : {} })
  setupWindow.on('closed', () => { setupWindow = undefined })
}

function createMenu() {
  const isMac = process.platform === 'darwin'
  const template = [
    ...(isMac ? [{ label: APP_NAME, submenu: [{ role: 'about' }, { type: 'separator' }, { role: 'quit' }] }] : []),
    { label: 'File', submenu: [
      { label: 'Change Database Connection…', click: () => { void openDatabaseSetup() } },
      { type: 'separator' },
      { label: 'Exit', accelerator: isMac ? 'Cmd+Q' : 'Alt+F4', click: () => app.quit() },
    ] },
    { label: 'View', submenu: [
      { role: 'reload' },
      { role: 'forceReload' },
      { type: 'separator' },
      { role: 'togglefullscreen' },
      ...(!app.isPackaged ? [{ role: 'toggledevtools' }] : []),
    ] },
    { label: 'Help', submenu: [
      { label: 'Documentation', click: () => shell.openExternal('https://github.com/amoghsonawanededsec/AI-Inventory-Prediction/blob/main/README.md') },
      { label: 'Check for Updates…', enabled: app.isPackaged, click: checkForUpdates },
      { type: 'separator' },
      { label: `About ${APP_NAME}`, click: () => dialog.showMessageBox(mainWindow || setupWindow, { title: `About ${APP_NAME}`, message: APP_NAME, detail: `Version ${app.getVersion()}\nInventory forecasting and operations desktop app.` }) },
    ] },
  ]

async function openDatabaseSetup() {
  await stopBackend()
  backendProcess = undefined
  backendPort = undefined
  if (mainWindow && !mainWindow.isDestroyed()) mainWindow.close()
  if (!setupWindow || setupWindow.isDestroyed()) createSetupWindow()
  setupWindow.focus()
}
  Menu.setApplicationMenu(Menu.buildFromTemplate(template))
}

async function checkForUpdates() {
  try {
    autoUpdater.autoDownload = false
    autoUpdater.autoInstallOnAppQuit = false
    const result = await autoUpdater.checkForUpdates()
    if (!result || result.updateInfo.version === app.getVersion()) {
      await dialog.showMessageBox(mainWindow, { type: 'info', title: APP_NAME, message: 'You are up to date.' })
      return
    }
    const { response } = await dialog.showMessageBox(mainWindow, { type: 'info', buttons: ['Download update', 'Later'], defaultId: 0, cancelId: 1, title: APP_NAME, message: `Version ${result.updateInfo.version} is available.`, detail: 'The update will download now and install when you choose to restart.' })
    if (response === 0) await autoUpdater.downloadUpdate()
  } catch (error) {
    writeLog('error', `Update check failed: ${error instanceof Error ? error.message : String(error)}`)
    await dialog.showMessageBox(mainWindow, { type: 'warning', title: APP_NAME, message: 'Could not check for updates.', detail: 'Check your internet connection and try again later.' })
  }
}

autoUpdater.on('update-downloaded', async () => {
  const { response } = await dialog.showMessageBox(mainWindow, { type: 'info', buttons: ['Restart and install', 'Later'], defaultId: 1, cancelId: 1, title: APP_NAME, message: 'The update is ready to install.', detail: 'Save your work before restarting.' })
  if (response === 0) autoUpdater.quitAndInstall()
})
autoUpdater.on('error', error => writeLog('error', `Auto-update error: ${error.message}`))

ipcMain.handle('desktop:save-database-url', async (_event, databaseUrl) => {
  if (!setupWindow || _event.sender !== setupWindow.webContents) return { ok: false, error: 'Database settings can only be changed from the setup window.' }
  try {
    const configuration = saveConfiguration(databaseUrl)
    await startBackend(configuration)
    if (setupWindow && !setupWindow.isDestroyed()) setupWindow.close()
    createMainWindow()
    return { ok: true }
  } catch (error) {
    writeLog('error', `Database connection setup failed: ${error instanceof Error ? error.message : String(error)}`)
    await stopBackend()
    backendProcess = undefined
    backendPort = undefined
    return { ok: false, error: error instanceof Error ? error.message : 'Could not start the local API service.' }
  }
})

app.on('web-contents-created', (_event, contents) => {
  contents.on('will-attach-webview', event => event.preventDefault())
})

app.whenReady().then(async () => {
  writeLog('info', `Starting ${APP_NAME} ${app.getVersion()}.`)
  createMenu()
  ipcMain.handle('desktop:get-api-base-url', (event) => {
    if (!mainWindow || event.sender !== mainWindow.webContents) throw new Error('The API address is only available to the app window.')
    if (!backendPort) throw new Error('The local API service is not ready.')
    return `http://127.0.0.1:${backendPort}`
  })
  try {
    const configuration = readConfiguration()
    if (configuration) {
      await startBackend(configuration)
      createMainWindow()
    } else {
      createSetupWindow()
    }
  } catch (error) {
    writeLog('error', `Startup failed: ${error instanceof Error ? error.message : String(error)}`)
    await stopBackend()
    backendProcess = undefined
    backendPort = undefined
    createSetupWindow(error instanceof Error ? error.message : 'Check the database settings, then enter the connection again.')
  }
})

app.on('before-quit', event => {
  if (isQuitting) return
  isQuitting = true
  if (backendProcess && backendProcess.exitCode === null) {
    event.preventDefault()
    void stopBackend().finally(() => app.quit())
  }
})
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit() })
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0 && backendPort) createMainWindow() })
app.on('render-process-gone', (_event, _contents, details) => writeLog('error', `Renderer process exited: ${details.reason}.`))
process.on('uncaughtException', error => writeLog('error', `Uncaught exception: ${error.stack || error.message}`))
process.on('unhandledRejection', reason => writeLog('error', `Unhandled rejection: ${String(reason)}`))
