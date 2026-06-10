/**
 * HiveFlow Studio - Electron 主进程
 * 负责管理应用窗口、启动后端服务、IPC 通信等
 */
import { app, BrowserWindow, ipcMain, dialog, Menu } from 'electron';
import * as path from 'path';
import { spawn, ChildProcess } from 'child_process';
import * as fs from 'fs';

let mainWindow: BrowserWindow | null = null;
let backendProcess: ChildProcess | null = null;

// 后端服务配置
const BACKEND_PORT = 8000;
const BACKEND_HOST = '127.0.0.1';
const BACKEND_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}`;

// 检查是否在开发模式
const isDev = !app.isPackaged;

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 700,
    title: 'HiveFlow Studio',
    icon: path.join(__dirname, '../public/icon.png'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
    backgroundColor: '#f5f5f5',
    show: false,
  });

  // 等待后端启动完成
  if (isDev) {
    // 开发模式：加载 Vite dev server
    mainWindow.loadURL('http://localhost:3000');
    mainWindow.webContents.openDevTools();
  } else {
    // 生产模式：加载打包后的静态文件
    mainWindow.loadFile(path.join(__dirname, '../build/index.html'));
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow?.show();
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // 自定义菜单
  createMenu();
}

function createMenu(): void {
  const template: Electron.MenuItemConstructorOptions[] = [
    {
      label: 'HiveFlow Studio',
      submenu: [
        { label: '关于 HiveFlow Studio', role: 'about' },
        { type: 'separator' },
        { label: '退出', accelerator: 'CmdOrCtrl+Q', click: () => app.quit() },
      ],
    },
    {
      label: '编辑',
      submenu: [
        { label: '撤销', role: 'undo' },
        { label: '重做', role: 'redo' },
        { type: 'separator' },
        { label: '剪切', role: 'cut' },
        { label: '复制', role: 'copy' },
        { label: '粘贴', role: 'paste' },
        { label: '全选', role: 'selectAll' },
      ],
    },
    {
      label: '视图',
      submenu: [
        { label: '刷新', role: 'reload' },
        { label: '切换开发者工具', role: 'toggleDevTools' },
        { type: 'separator' },
        { label: '放大', role: 'zoomIn' },
        { label: '缩小', role: 'zoomOut' },
        { label: '重置缩放', role: 'resetZoom' },
        { label: '全屏', role: 'togglefullscreen' },
      ],
    },
    {
      label: '帮助',
      submenu: [
        { label: '查看文档', click: () => openExternal('https://github.com/HiveFlow') },
      ],
    },
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

function openExternal(url: string): void {
  const { shell } = require('electron');
  shell.openExternal(url);
}

// 启动后端服务
function startBackend(): Promise<void> {
  return new Promise((resolve, reject) => {
    const backendDir = isDev
      ? path.join(__dirname, '../../backend')
      : path.join(process.resourcesPath, 'backend');

    const pythonCmd = isDev ? 'python' : path.join(process.resourcesPath, 'python', 'python.exe');

    console.log(`Starting backend from: ${backendDir}`);
    console.log(`Python command: ${pythonCmd}`);

    backendProcess = spawn(pythonCmd, [
      '-m', 'uvicorn', 'app.main:app',
      '--host', BACKEND_HOST,
      '--port', String(BACKEND_PORT),
    ], {
      cwd: backendDir,
      env: {
        ...process.env,
        PYTHONPATH: backendDir,
      },
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    backendProcess.stdout?.on('data', (data) => {
      const msg = data.toString();
      console.log(`[Backend] ${msg}`);
      if (msg.includes('Application startup complete') || msg.includes('Uvicorn running')) {
        resolve();
      }
    });

    backendProcess.stderr?.on('data', (data) => {
      console.error(`[Backend Error] ${data.toString()}`);
    });

    backendProcess.on('error', (err) => {
      console.error('Failed to start backend:', err);
      reject(err);
    });

    backendProcess.on('exit', (code) => {
      console.log(`Backend exited with code ${code}`);
    });

    // 超时处理
    setTimeout(() => {
      if (backendProcess?.exitCode === null) {
        reject(new Error('Backend startup timeout'));
      }
    }, 30000);
  });
}

// 停止后端服务
function stopBackend(): void {
  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
    console.log('Backend stopped');
  }
}

// IPC 处理
function setupIpc(): void {
  // 获取后端 URL
  ipcMain.handle('get-backend-url', () => BACKEND_URL);

  // 退出应用
  ipcMain.on('quit-app', () => {
    stopBackend();
    app.quit();
  });

  // 文件对话框
  ipcMain.handle('show-open-dialog', async (_event, options) => {
    if (!mainWindow) return { canceled: true };
    return dialog.showOpenDialog(mainWindow, options);
  });

  ipcMain.handle('show-save-dialog', async (_event, options) => {
    if (!mainWindow) return { canceled: true };
    return dialog.showSaveDialog(mainWindow, options);
  });

  // 读取文件
  ipcMain.handle('read-file', async (_event, filePath: string) => {
    return fs.readFileSync(filePath, 'utf-8');
  });

  // 写入文件
  ipcMain.handle('write-file', async (_event, filePath: string, content: string) => {
    fs.writeFileSync(filePath, content, 'utf-8');
    return true;
  });
}

// 应用生命周期
app.whenReady().then(async () => {
  setupIpc();

  // 启动后端服务
  try {
    await startBackend();
    console.log('Backend started successfully');
  } catch (err) {
    console.error('Failed to start backend:', err);
    dialog.showErrorBox(
      '后端启动失败',
      'HiveFlow Studio 后端服务启动失败，请检查 Python 环境是否正确安装。\n\n错误信息: ' + String(err)
    );
  }

  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  stopBackend();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  stopBackend();
});
