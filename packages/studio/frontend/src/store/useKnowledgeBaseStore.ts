import { create } from 'zustand';
import type { KnowledgeBase, DocumentDef } from '@/types';
import { apiFetch } from '@/utils/api';
import { useEngineStore } from '@/store/useEngineStore';

interface KnowledgeBaseState {
  knowledgeBases: KnowledgeBase[];
  selectedKbId: string | null;
  loading: boolean;
  useApi: boolean;

  fetchKnowledgeBases: () => Promise<void>;
  createKnowledgeBase: (data: { name: string; description?: string; embedding_model?: string }) => Promise<KnowledgeBase>;
  updateKnowledgeBase: (id: string, updates: Partial<KnowledgeBase>) => void;
  deleteKnowledgeBase: (id: string) => Promise<void>;
  getKnowledgeBase: (id: string) => KnowledgeBase | undefined;

  addDocument: (kbId: string, doc: Omit<DocumentDef, 'id' | 'created_at'>) => Promise<void>;
  removeDocument: (kbId: string, docId: string) => Promise<void>;
  updateDocumentStatus: (kbId: string, docId: string, status: DocumentDef['status'], chunksCount?: number) => void;

  updateChunkConfig: (kbId: string, chunkSize: number, chunkOverlap: number) => void;
  startEmbedding: (kbId: string) => Promise<void>;
  searchDocuments: (kbId: string, query: string) => Promise<{ document: string; score: number; chunk: string }[]>;

  selectKnowledgeBase: (id: string | null) => void;
  reset: () => void;
}

let nextKbId = 1;
let nextDocId = 1;

function mapApiKb(raw: {
  kb_id: string;
  name: string;
  description?: string;
  doc_count?: number;
  vector_store?: string;
  created_at?: number;
}): KnowledgeBase {
  return {
    id: raw.kb_id,
    name: raw.name,
    description: raw.description || '',
    documents: [],
    embedding_model: 'dummy',
    chunk_size: 512,
    chunk_overlap: 50,
    created_at: raw.created_at ? raw.created_at * 1000 : Date.now(),
    updated_at: Date.now(),
    doc_count: raw.doc_count,
  };
}

function shouldUseApi(): boolean {
  return useEngineStore.getState().mode === 'real';
}

export const useKnowledgeBaseStore = create<KnowledgeBaseState>((set, get) => ({
  knowledgeBases: [],
  selectedKbId: null,
  loading: false,
  useApi: false,

  fetchKnowledgeBases: async () => {
    if (!shouldUseApi()) {
      set({ useApi: false });
      return;
    }
    set({ loading: true, useApi: true });
    try {
      const data = await apiFetch('/api/knowledge');
      const kbs = (data.knowledge_bases || []).map(mapApiKb);
      set({ knowledgeBases: kbs, loading: false });
    } catch {
      set({ loading: false, useApi: false });
    }
  },

  createKnowledgeBase: async (data) => {
    const kbId = `kb_${nextKbId++}`;
    if (shouldUseApi()) {
      await apiFetch('/api/knowledge', {
        method: 'POST',
        body: JSON.stringify({
          kb_id: kbId,
          name: data.name,
          description: data.description || '',
        }),
      });
      await get().fetchKnowledgeBases();
      const kb = get().getKnowledgeBase(kbId);
      if (kb) return kb;
    }

    const now = Date.now();
    const kb: KnowledgeBase = {
      id: kbId,
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

  deleteKnowledgeBase: async (id) => {
    if (shouldUseApi()) {
      await apiFetch(`/api/knowledge/${id}`, { method: 'DELETE' });
      await get().fetchKnowledgeBases();
      return;
    }
    set((s) => ({
      knowledgeBases: s.knowledgeBases.filter((kb) => kb.id !== id),
      selectedKbId: s.selectedKbId === id ? null : s.selectedKbId,
    }));
  },

  getKnowledgeBase: (id) => get().knowledgeBases.find((kb) => kb.id === id),

  addDocument: async (kbId, doc) => {
    if (shouldUseApi()) {
      await apiFetch(`/api/knowledge/${kbId}/documents`, {
        method: 'POST',
        body: JSON.stringify({
          content: doc.content || doc.name,
          doc_type: 'text',
          metadata: { name: doc.name },
        }),
      });
      const list = await apiFetch(`/api/knowledge/${kbId}/documents`);
      const docs: DocumentDef[] = (list.documents || []).map((d: { doc_id: string; preview?: string; metadata?: { name?: string }; chunk_count?: number }) => ({
        id: d.doc_id,
        name: d.metadata?.name || d.doc_id,
        type: 'text',
        size: (d.preview || '').length,
        status: 'completed' as const,
        chunks_count: d.chunk_count,
        created_at: Date.now(),
      }));
      set((s) => ({
        knowledgeBases: s.knowledgeBases.map((kb) =>
          kb.id === kbId ? { ...kb, documents: docs, updated_at: Date.now() } : kb
        ),
      }));
      return;
    }

    const newDoc: DocumentDef = {
      ...doc,
      id: `doc_${nextDocId++}`,
      created_at: Date.now(),
    };
    set((s) => ({
      knowledgeBases: s.knowledgeBases.map((kb) =>
        kb.id === kbId ? { ...kb, documents: [...kb.documents, newDoc], updated_at: Date.now() } : kb
      ),
    }));
  },

  removeDocument: async (kbId, docId) => {
    if (shouldUseApi()) {
      await apiFetch(`/api/knowledge/${kbId}/documents/${docId}`, { method: 'DELETE' });
      const list = await apiFetch(`/api/knowledge/${kbId}/documents`);
      const docs: DocumentDef[] = (list.documents || []).map((d: { doc_id: string; preview?: string; metadata?: { name?: string }; chunk_count?: number }) => ({
        id: d.doc_id,
        name: d.metadata?.name || d.doc_id,
        type: 'text',
        size: (d.preview || '').length,
        status: 'completed' as const,
        chunks_count: d.chunk_count,
        created_at: Date.now(),
      }));
      set((s) => ({
        knowledgeBases: s.knowledgeBases.map((kb) =>
          kb.id === kbId ? { ...kb, documents: docs, updated_at: Date.now() } : kb
        ),
      }));
      return;
    }
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
                d.id === docId ? { ...d, status, chunks_count: chunksCount ?? d.chunks_count } : d
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
        kb.id === kbId ? { ...kb, chunk_size: chunkSize, chunk_overlap: chunkOverlap, updated_at: Date.now() } : kb
      ),
    }));
  },

  startEmbedding: async (kbId) => {
    const kb = get().knowledgeBases.find((k) => k.id === kbId);
    if (!kb) return;

    const pendingDocs = kb.documents.filter((d) => d.status === 'pending');
    pendingDocs.forEach((d) => get().updateDocumentStatus(kbId, d.id, 'processing'));

    if (shouldUseApi()) {
      for (const doc of pendingDocs) {
        try {
          await apiFetch(`/api/knowledge/${kbId}/documents`, {
            method: 'POST',
            body: JSON.stringify({
              content: doc.content || doc.name,
              doc_type: 'text',
              metadata: { name: doc.name },
            }),
          });
          get().updateDocumentStatus(kbId, doc.id, 'completed', Math.max(1, Math.floor(doc.size / kb.chunk_size)));
        } catch {
          get().updateDocumentStatus(kbId, doc.id, 'failed');
        }
      }
      return;
    }

    pendingDocs.forEach((doc) => {
      const delay = 1000 + Math.random() * 3000;
      setTimeout(() => {
        const chunkCount = Math.max(1, Math.floor(doc.size / kb.chunk_size));
        get().updateDocumentStatus(kbId, doc.id, 'completed', chunkCount);
      }, delay);
    });
  },

  searchDocuments: async (kbId, query) => {
    if (shouldUseApi()) {
      try {
        const data = await apiFetch(`/api/knowledge/${kbId}/search`, {
          method: 'POST',
          body: JSON.stringify({ query, top_k: 5 }),
        });
        return (data.results || []).map((r: { content: string; score: number; doc_id?: string }) => ({
          document: r.doc_id || 'document',
          score: r.score,
          chunk: r.content,
        }));
      } catch {
        return [];
      }
    }

    const kb = get().knowledgeBases.find((k) => k.id === kbId);
    if (!kb) return [];
    const completedDocs = kb.documents.filter((d) => d.status === 'completed');
    return completedDocs.flatMap((doc) => {
      const numChunks = doc.chunks_count || 1;
      return Array.from({ length: Math.min(numChunks, 3) }, (_, i) => ({
        document: doc.name,
        score: Math.max(0.3, 0.95 - Math.random() * 0.3),
        chunk: `[${doc.name}] fragment ${i + 1} — ${query}`,
      }));
    }).sort((a, b) => b.score - a.score).slice(0, 5);
  },

  selectKnowledgeBase: (id) => set({ selectedKbId: id }),

  reset: () => {
    set({ knowledgeBases: [], selectedKbId: null, loading: false, useApi: false });
    nextKbId = 1;
    nextDocId = 1;
  },
}));
