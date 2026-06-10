export interface ElectronAPI {
  getBackendUrl: () => Promise<string>;
  quitApp: () => void;
  showOpenDialog: (options: any) => Promise<any>;
  showSaveDialog: (options: any) => Promise<any>;
  readFile: (filePath: string) => Promise<string>;
  writeFile: (filePath: string, content: string) => Promise<boolean>;
  platform: string;
  isPackaged: boolean;
}

declare global {
  interface Window {
    electronAPI: ElectronAPI;
  }
}

export {};
