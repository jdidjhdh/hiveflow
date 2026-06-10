import type { Node, Edge } from 'reactflow';
import type { WorkflowNodeData } from '@/types';

const DB_NAME = 'HiveFlowStudio';
const DB_VERSION = 1;
const STORE_WORKFLOWS = 'workflows';
const STORE_SETTINGS = 'settings';

interface WorkflowDoc {
  id: string;
  name: string;
  nodes: Node<WorkflowNodeData>[];
  edges: Edge[];
  createdAt: number;
  updatedAt: number;
}

interface SettingDoc {
  key: string;
  value: any;
}

class IndexedDBManager {
  private db: IDBDatabase | null = null;
  private initPromise: Promise<void> | null = null;

  async init(): Promise<void> {
    if (this.db) return;
    if (this.initPromise) return this.initPromise;

    this.initPromise = new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        if (!db.objectStoreNames.contains(STORE_WORKFLOWS)) {
          const wfStore = db.createObjectStore(STORE_WORKFLOWS, { keyPath: 'id' });
          wfStore.createIndex('updatedAt', 'updatedAt', { unique: false });
        }
        if (!db.objectStoreNames.contains(STORE_SETTINGS)) {
          db.createObjectStore(STORE_SETTINGS, { keyPath: 'key' });
        }
      };

      request.onsuccess = (event) => {
        this.db = (event.target as IDBOpenDBRequest).result;
        resolve();
      };

      request.onerror = () => {
        reject(new Error('Failed to open IndexedDB'));
      };
    });

    return this.initPromise;
  }

  // ========== 工作流 CRUD ==========

  async saveWorkflow(data: WorkflowDoc): Promise<void> {
    await this.init();
    return new Promise((resolve, reject) => {
      const tx = this.db!.transaction(STORE_WORKFLOWS, 'readwrite');
      const store = tx.objectStore(STORE_WORKFLOWS);
      store.put(data);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  async getWorkflow(id: string): Promise<WorkflowDoc | undefined> {
    await this.init();
    return new Promise((resolve, reject) => {
      const tx = this.db!.transaction(STORE_WORKFLOWS, 'readonly');
      const store = tx.objectStore(STORE_WORKFLOWS);
      const request = store.get(id);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async getAllWorkflows(): Promise<WorkflowDoc[]> {
    await this.init();
    return new Promise((resolve, reject) => {
      const tx = this.db!.transaction(STORE_WORKFLOWS, 'readonly');
      const store = tx.objectStore(STORE_WORKFLOWS);
      const request = store.getAll();
      request.onsuccess = () => resolve(request.result || []);
      request.onerror = () => reject(request.error);
    });
  }

  async deleteWorkflow(id: string): Promise<void> {
    await this.init();
    return new Promise((resolve, reject) => {
      const tx = this.db!.transaction(STORE_WORKFLOWS, 'readwrite');
      const store = tx.objectStore(STORE_WORKFLOWS);
      store.delete(id);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  // ========== 设置 CRUD ==========

  async saveSetting(key: string, value: any): Promise<void> {
    await this.init();
    return new Promise((resolve, reject) => {
      const tx = this.db!.transaction(STORE_SETTINGS, 'readwrite');
      const store = tx.objectStore(STORE_SETTINGS);
      store.put({ key, value });
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  async getSetting<T>(key: string): Promise<T | undefined> {
    await this.init();
    return new Promise((resolve, reject) => {
      const tx = this.db!.transaction(STORE_SETTINGS, 'readonly');
      const store = tx.objectStore(STORE_SETTINGS);
      const request = store.get(key);
      request.onsuccess = () => resolve(request.result?.value);
      request.onerror = () => reject(request.error);
    });
  }

  async deleteSetting(key: string): Promise<void> {
    await this.init();
    return new Promise((resolve, reject) => {
      const tx = this.db!.transaction(STORE_SETTINGS, 'readwrite');
      const store = tx.objectStore(STORE_SETTINGS);
      store.delete(key);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  // ========== 批量操作 ==========

  async exportAll(): Promise<{ workflows: WorkflowDoc[]; settings: SettingDoc[] }> {
    await this.init();
    const workflows = await this.getAllWorkflows();

    return new Promise((resolve, reject) => {
      const tx = this.db!.transaction(STORE_SETTINGS, 'readonly');
      const store = tx.objectStore(STORE_SETTINGS);
      const request = store.getAll();
      request.onsuccess = () => resolve({ workflows, settings: request.result || [] });
      request.onerror = () => reject(request.error);
    });
  }

  async importAll(data: { workflows: WorkflowDoc[]; settings: SettingDoc[] }): Promise<void> {
    await this.init();

    // 导入工作流
    const wfTx = this.db!.transaction(STORE_WORKFLOWS, 'readwrite');
    const wfStore = wfTx.objectStore(STORE_WORKFLOWS);
    for (const wf of data.workflows) {
      wfStore.put(wf);
    }

    // 导入设置
    const settingsTx = this.db!.transaction(STORE_SETTINGS, 'readwrite');
    const settingsStore = settingsTx.objectStore(STORE_SETTINGS);
    for (const setting of data.settings) {
      settingsStore.put(setting);
    }

    return new Promise((resolve, reject) => {
      settingsTx.oncomplete = () => resolve();
      settingsTx.onerror = () => reject(settingsTx.error);
    });
  }
}

// 单例
const dbManager = new IndexedDBManager();
export default dbManager;
