/**
 * HiveFlow Studio - Electron 预加载脚本
 * 为渲染进程提供安全的 IPC 接口
 */
import { contextBridge, ipcRenderer } from 'electron';

// 暴露安全的 API 到渲染进程
contextBridge.exposeInMainWorld('electronAPI', {
  // 获取后端 URL
  getBackendUrl: () => ipcRenderer.invoke('get-backend-url'),

  // 退出应用
  quitApp: () => ipcRenderer.send('quit-app'),

  // 文件对话框
  showOpenDialog: (options: any) => ipcRenderer.invoke('show-open-dialog', options),
  showSaveDialog: (options: any) => ipcRenderer.invoke('show-save-dialog', options),

  // 文件操作
  readFile: (filePath: string) => ipcRenderer.invoke('read-file', filePath),
  writeFile: (filePath: string, content: string) => ipcRenderer.invoke('write-file', filePath, content),

  // 应用信息
  platform: process.platform,
  isPackaged: process.env.NODE_ENV === 'production',
});
