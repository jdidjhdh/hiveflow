import { create } from 'zustand';
import type { KnowledgeBase, DocumentDef } from '@/types';
import { useEngineStore } from '@/store/useEngineStore';

interface KnowledgeBaseState {
  knowledgeBases: KnowledgeBase[];
  selectedKbId: string | null;
  loading: boolean;

  // KB CRUD
  createKnowledgeBase: (data: { name: string; description?: string; embedding_model?: string }) => KnowledgeBase;
  updateKnowledgeBase: (id: string, updates: Partial<KnowledgeBase>) => void;
  deleteKnowledgeBase: (id: string) => void;
  getKnowledgeBase: (id: string) => KnowledgeBase | undefined;

  // Document management
  addDocument: (kbId: string, doc: Omit<DocumentDef, 'id' | 'created_at'>) => void;
  removeDocument: (kbId: string, docId: string) => void;
  updateDocumentStatus: (kbId: string, docId: string, status: DocumentDef['status'], chunksCount?: number) => void;

  // Chunking config
  updateChunkConfig: (kbId: string, chunkSize: number, chunkOverlap: number) => void;

  // Embedding simulation
  startEmbedding: (kbId: string) => void;

  // Search test
  searchDocuments: (kbId: string, query: string) => { document: string; score: number; chunk: string }[];

  // Selection
  selectKnowledgeBase: (id: string | null) => void;

  // Reset
  reset: () => void;
}

let nextKbId = 1;
let nextDocId = 1;

export const useKnowledgeBaseStore = create<KnowledgeBaseState>((set, get) => ({
  knowledgeBases: [],
  selectedKbId: null,
  loading: false,

  createKnowledgeBase: (data) => {
    const now = Date.now();
    const kb: KnowledgeBase = {
      id: `kb_${nextKbId++}`,
      name: data.name,
      description: data.description || '',
      documents: [],
      embedding_model: data.embedding_model || 'text-embedding-ada-002',
      chunk_size: 512,
      chunk_overlap: 50,
      created_at: now,
      updated_at: now,
    };
    set((s) => ({ knowledgeBases: [...s.knowledgeBases, kb] }));
    return kb;
  },

  updateKnowledgeBase: (id, updates) => {
    set((s) => ({
      knowledgeBases: s.knowledgeBases.map((kb) =>
        kb.id === id ? { ...kb, ...updates, updated_at: Date.now() } : kb
      ),
    }));
  },

  deleteKnowledgeBase: (id) => {
    set((s) => ({
      knowledgeBases: s.knowledgeBases.filter((kb) => kb.id !== id),
      selectedKbId: s.selectedKbId === id ? null : s.selectedKbId,
    }));
  },

  getKnowledgeBase: (id) => {
    return get().knowledgeBases.find((kb) => kb.id === id);
  },

  addDocument: (kbId, doc) => {
    const newDoc: DocumentDef = {
      ...doc,
      id: `doc_${nextDocId++}`,
      created_at: Date.now(),
    };
    set((s) => ({
      knowledgeBases: s.knowledgeBases.map((kb) =>
        kb.id === kbId
          ? { ...kb, documents: [...kb.documents, newDoc], updated_at: Date.now() }
          : kb
      ),
    }));
  },

  removeDocument: (kbId, docId) => {
    set((s) => ({
      knowledgeBases: s.knowledgeBases.map((kb) =>
        kb.id === kbId
          ? { ...kb, documents: kb.documents.filter((d) => d.id !== docId), updated_at: Date.now() }
          : kb
      ),
    }));
  },

  updateDocumentStatus: (kbId, docId, status, chunksCount) => {
    set((s) => ({
      knowledgeBases: s.knowledgeBases.map((kb) =>
        kb.id === kbId
          ? {
              ...kb,
              documents: kb.documents.map((d) =>
                d.id === docId
                  ? { ...d, status, chunks_count: chunksCount ?? d.chunks_count }
                  : d
              ),
              updated_at: Date.now(),
            }
          : kb
      ),
    }));
  },

  updateChunkConfig: (kbId, chunkSize, chunkOverlap) => {
    set((s) => ({
      knowledgeBases: s.knowledgeBases.map((kb) =>
        kb.id === kbId
          ? { ...kb, chunk_size: chunkSize, chunk_overlap: chunkOverlap, updated_at: Date.now() }
          : kb
      ),
    }));
  },

  startEmbedding: (kbId) => {
    const engine = useEngineStore.getState().getEngine();
    const kb = get().knowledgeBases.find((k) => k.id === kbId);
    if (!kb) return;

    // Set all pending documents to processing
    const pendingDocs = kb.documents.filter((d) => d.status === 'pending');
    pendingDocs.forEach((d) => {
      get().updateDocumentStatus(kbId, d.id, 'processing');
    });

    // Simulate embedding process
    pendingDocs.forEach((doc) => {
      const delay = 1000 + Math.random() * 3000;
      setTimeout(() => {
        const chunkCount = Math.max(1, Math.floor(doc.size / kb.chunk_size));
        get().updateDocumentStatus(kbId, doc.id, 'completed', chunkCount);
      }, delay);
    });
  },

  searchDocuments: (kbId, query) => {
    const kb = get().knowledgeBases.find((k) => k.id === kbId);
    if (!kb) return [];

    const completedDocs = kb.documents.filter((d) => d.status === 'completed');
    const queryLower = query.toLowerCase();

    // Mock vector search — simulate semantic similarity
    return completedDocs.flatMap((doc) => {
      const numChunks = doc.chunks_count || 1;
      return Array.from({ length: Math.min(numChunks, 3) }, (_, i) => ({
        document: doc.name,
        score: Math.max(0.3, 0.95 - Math.random() * 0.3),
        chunk: `[${doc.name}] 片段 ${i + 1} — ${query} 相关内容...（模拟检索结果）`,
      }));
    }).sort((a, b) => b.score - a.score).slice(0, 5);
  },

  selectKnowledgeBase: (id) => {
    set({ selectedKbId: id });
  },

  reset: () => {
    set({ knowledgeBases: [], selectedKbId: null, loading: false });
    nextKbId = 1;
    nextDocId = 1;
  },
}));
