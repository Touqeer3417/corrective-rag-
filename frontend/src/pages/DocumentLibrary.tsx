import { useEffect, useState } from 'react';
import { Trash2, FileText, Search, Filter, ArrowUpDown } from 'lucide-react';
import { useDocumentStore } from '../stores/documentStore';
import { deleteDocument } from '../services/documents';

export default function DocumentLibrary() {
  const { documents, loading, fetchDocuments, removeDocument } = useDocumentStore();
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<'name' | 'date' | 'chunks'>('date');
  const [filterStatus, setFilterStatus] = useState<string>('all');

  useEffect(() => { fetchDocuments(); }, []);

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this document?')) return;
    await deleteDocument(id);
    removeDocument(id);
  };

  const filteredDocs = documents
    .filter((d) => {
      const matchesSearch = d.original_name.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesFilter = filterStatus === 'all' || d.status === filterStatus;
      return matchesSearch && matchesFilter;
    })
    .sort((a, b) => {
      if (sortBy === 'name') return a.original_name.localeCompare(b.original_name);
      if (sortBy === 'chunks') return b.chunk_count - a.chunk_count;
      return new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime();
    });

  return (
    <div className="space-y-6 px-4 py-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold bg-gradient-to-r from-cyan-400 via-violet-400 to-emerald-400 bg-clip-text text-transparent">
            Document Library
          </h2>
          <p className="text-slate-400 text-sm mt-1">{documents.length} documents in your knowledge base</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              type="text"
              placeholder="Search documents..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 pr-4 py-2.5 rounded-xl bg-slate-900/60 border border-slate-700/50 text-slate-200 text-sm placeholder-slate-500 outline-none focus:border-cyan-500/40 focus:ring-1 focus:ring-cyan-500/20 transition-all w-64"
            />
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        {['all', 'indexed', 'processing', 'pending', 'error'].map((status) => (
          <button
            key={status}
            onClick={() => setFilterStatus(status)}
            className={`px-3.5 py-1.5 rounded-full text-xs font-medium capitalize transition-all duration-300 border ${
              filterStatus === status
                ? 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30 shadow-[0_0_12px_rgba(6,182,212,0.15)]'
                : 'bg-slate-900/40 text-slate-400 border-slate-700/40 hover:border-slate-600 hover:text-slate-300'
            }`}
          >
            {status}
          </button>
        ))}
        <div className="h-6 w-px bg-slate-700/50 mx-1" />
        <button
          onClick={() => setSortBy(sortBy === 'date' ? 'name' : sortBy === 'name' ? 'chunks' : 'date')}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium text-slate-400 border border-slate-700/40 hover:border-slate-600 hover:text-slate-300 transition-all"
        >
          <ArrowUpDown size={12} />
          Sort by {sortBy}
        </button>
      </div>

      {/* Table */}
      <div className="rounded-2xl border border-slate-700/50 bg-slate-900/40 backdrop-blur-xl overflow-hidden shadow-[0_0_40px_rgba(0,0,0,0.2)]">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-slate-700/40 bg-slate-800/30">
                <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Document</th>
                <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Type</th>
                <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Chunks</th>
                <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Status</th>
                <th className="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/30">
              {filteredDocs.map((doc, index) => (
                <tr
                  key={doc.document_id}
                  className="hover:bg-slate-800/30 transition-all duration-300 group"
                  style={{ animationDelay: `${index * 30}ms` }}
                >
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-4">
                      <div className="p-2.5 rounded-xl bg-slate-800/50 border border-slate-700/40 group-hover:border-cyan-500/30 group-hover:bg-cyan-500/5 transition-all duration-300">
                        <FileText size={18} className="text-slate-400 group-hover:text-cyan-400 transition-colors" />
                      </div>
                      <div>
                        <p className="font-medium text-slate-200 group-hover:text-cyan-300 transition-colors text-sm">{doc.original_name}</p>
                        <p className="text-xs text-slate-500 mt-0.5">{formatDate(doc.created_at)}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center px-2.5 py-1 rounded-md bg-slate-800/50 border border-slate-700/40 text-xs font-medium text-slate-400 uppercase">
                      {doc.file_type}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 rounded-full bg-slate-700/50 overflow-hidden">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-violet-500"
                          style={{ width: `${Math.min((doc.chunk_count / 50) * 100, 100)}%` }}
                        />
                      </div>
                      <span className="text-sm text-slate-400">{doc.chunk_count}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <StatusBadge status={doc.status} />
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button
                      onClick={() => handleDelete(doc.document_id)}
                      className="p-2 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 hover:border-rose-500/20 border border-transparent transition-all duration-300"
                      title="Delete document"
                    >
                      <Trash2 size={16} />
                    </button>
                  </td>
                </tr>
              ))}
              {filteredDocs.length === 0 && !loading && (
                <tr>
                  <td colSpan={5} className="px-6 py-16 text-center">
                    <div className="relative inline-block mb-4">
                      <div className="absolute inset-0 bg-slate-500/10 blur-xl rounded-full" />
                      <Filter size={40} className="relative text-slate-600" />
                    </div>
                    <p className="text-slate-500">No documents found</p>
                    <p className="text-slate-600 text-sm mt-1">Try adjusting your search or filters</p>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, { bg: string; border: string; text: string; dot: string }> = {
    indexed: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/20', text: 'text-emerald-400', dot: 'bg-emerald-400' },
    pending: { bg: 'bg-slate-500/10', border: 'border-slate-500/20', text: 'text-slate-400', dot: 'bg-slate-400' },
    processing: { bg: 'bg-amber-500/10', border: 'border-amber-500/20', text: 'text-amber-400', dot: 'bg-amber-400' },
    error: { bg: 'bg-rose-500/10', border: 'border-rose-500/20', text: 'text-rose-400', dot: 'bg-rose-400' },
  };
  const s = styles[status] || styles.pending;

  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border ${s.bg} ${s.border} ${s.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${s.dot} ${status === 'processing' ? 'animate-pulse' : ''}`} />
      {status}
    </span>
  );
}

function formatDate(dateString?: string) {
  if (!dateString) return 'Recently';
  const date = new Date(dateString);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const hours = Math.floor(diff / (1000 * 60 * 60));
  if (hours < 1) return 'Just now';
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}