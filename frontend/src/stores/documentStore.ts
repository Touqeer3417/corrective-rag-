import { create } from 'zustand';
import { DocumentInfo } from '../types/document';

interface DocumentStore {
  documents: DocumentInfo[];
  loading: boolean;
  fetchDocuments: () => Promise<void>;
  removeDocument: (id: string) => void;
  addDocument: (doc: DocumentInfo) => void;
}

export const useDocumentStore = create<DocumentStore>((set, get) => ({
  documents: [],
  loading: false,
  fetchDocuments: async () => {
    set({ loading: true });
    try {
      const res = await fetch('http://localhost:8000/api/v1/documents');
      const data = await res.json();
      set({ documents: data.documents || [], loading: false });
    } catch (e) {
      set({ loading: false });
    }
  },
  removeDocument: (id) => {
    set({ documents: get().documents.filter((d) => d.document_id !== id) });
  },
  addDocument: (doc) => {
    set({ documents: [doc, ...get().documents] });
  },
}));
