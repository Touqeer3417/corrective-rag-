import { useEffect, useState } from 'react';
import { FileText, CheckCircle, Clock, AlertCircle, TrendingUp, Activity } from 'lucide-react';
import { useDocumentStore } from '../stores/documentStore';

export default function Dashboard() {
  const { documents, fetchDocuments } = useDocumentStore();
  useEffect(() => { fetchDocuments(); }, []);

  const total = documents.length;
  const indexed = documents.filter((d) => d.status === 'indexed').length;
  const pending = documents.filter((d) => d.status === 'pending' || d.status === 'processing').length;
  const errors = documents.filter((d) => d.status === 'error').length;

  return (
    <div className="space-y-8 px-4 py-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold bg-gradient-to-r from-cyan-400 via-violet-400 to-emerald-400 bg-clip-text text-transparent">
            Dashboard
          </h2>
          <p className="text-slate-400 text-sm mt-1">Overview of your knowledge base</p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-medium">
          <Activity size={14} className="animate-pulse" />
          System Active
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        <StatCard
          icon={<FileText size={22} />}
          label="Total Documents"
          value={total}
          color="cyan"
          trend="+12%"
        />
        <StatCard
          icon={<CheckCircle size={22} />}
          label="Indexed"
          value={indexed}
          color="emerald"
          trend="98%"
        />
        <StatCard
          icon={<Clock size={22} />}
          label="Pending"
          value={pending}
          color="amber"
          trend="Processing"
        />
        <StatCard
          icon={<AlertCircle size={22} />}
          label="Errors"
          value={errors}
          color="rose"
          trend={errors === 0 ? 'All Good' : 'Needs Attention'}
        />
      </div>

      {/* Recent Uploads */}
      <div className="rounded-2xl border border-slate-700/50 bg-slate-900/40 backdrop-blur-xl overflow-hidden shadow-[0_0_40px_rgba(0,0,0,0.2)]">
        <div className="px-6 py-5 border-b border-slate-700/40 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-violet-500/10 border border-violet-500/20">
              <TrendingUp size={18} className="text-violet-400" />
            </div>
            <h3 className="text-lg font-semibold text-slate-100">Recent Uploads</h3>
          </div>
          <span className="text-xs text-slate-500 bg-slate-800/50 px-2.5 py-1 rounded-full border border-slate-700/40">
            Last 5 documents
          </span>
        </div>

        {documents.length === 0 ? (
          <div className="px-6 py-16 text-center">
            <div className="relative inline-block mb-4">
              <div className="absolute inset-0 bg-slate-500/10 blur-xl rounded-full" />
              <FileText size={40} className="relative text-slate-600" />
            </div>
            <p className="text-slate-500">No documents uploaded yet</p>
            <p className="text-slate-600 text-sm mt-1">Upload documents to build your knowledge base</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-700/30">
            {documents.slice(0, 5).map((doc, index) => (
              <div
                key={doc.document_id}
                className="px-6 py-4 flex justify-between items-center hover:bg-slate-800/30 transition-colors duration-300 group"
                style={{ animationDelay: `${index * 50}ms` }}
              >
                <div className="flex items-center gap-4">
                  <div className="p-2.5 rounded-xl bg-slate-800/50 border border-slate-700/40 group-hover:border-cyan-500/30 group-hover:bg-cyan-500/5 transition-all duration-300">
                    <FileText size={18} className="text-slate-400 group-hover:text-cyan-400 transition-colors" />
                  </div>
                  <div>
                    <p className="font-medium text-slate-200 group-hover:text-cyan-300 transition-colors">{doc.original_name}</p>
                    <p className="text-sm text-slate-500 mt-0.5">
                      {doc.file_type.toUpperCase()} · {doc.chunk_count} chunks · {formatDate(doc.created_at)}
                    </p>
                  </div>
                </div>
                <StatusBadge status={doc.status} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ icon, label, value, color, trend }: {
  icon: React.ReactNode;
  label: string;
  value: number;
  color: 'cyan' | 'emerald' | 'amber' | 'rose';
  trend: string;
}) {
  const [displayValue, setDisplayValue] = useState(0);

  useEffect(() => {
    const duration = 800;
    const steps = 30;
    const increment = value / steps;
    let current = 0;
    const timer = setInterval(() => {
      current += increment;
      if (current >= value) {
        setDisplayValue(value);
        clearInterval(timer);
      } else {
        setDisplayValue(Math.floor(current));
      }
    }, duration / steps);
    return () => clearInterval(timer);
  }, [value]);

  const colorMap = {
    cyan: { bg: 'bg-cyan-500/10', border: 'border-cyan-500/20', text: 'text-cyan-400', glow: 'shadow-[0_0_20px_rgba(6,182,212,0.1)]', gradient: 'from-cyan-500/20 to-transparent' },
    emerald: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/20', text: 'text-emerald-400', glow: 'shadow-[0_0_20px_rgba(16,185,129,0.1)]', gradient: 'from-emerald-500/20 to-transparent' },
    amber: { bg: 'bg-amber-500/10', border: 'border-amber-500/20', text: 'text-amber-400', glow: 'shadow-[0_0_20px_rgba(245,158,11,0.1)]', gradient: 'from-amber-500/20 to-transparent' },
    rose: { bg: 'bg-rose-500/10', border: 'border-rose-500/20', text: 'text-rose-400', glow: 'shadow-[0_0_20px_rgba(244,63,94,0.1)]', gradient: 'from-rose-500/20 to-transparent' },
  };

  const c = colorMap[color];

  return (
    <div className={`relative rounded-2xl border ${c.border} bg-slate-900/40 backdrop-blur-xl p-5 ${c.glow} hover:scale-[1.02] transition-all duration-300 group overflow-hidden`}>
      <div className={`absolute top-0 right-0 w-32 h-32 bg-gradient-to-br ${c.gradient} rounded-full blur-2xl opacity-50 group-hover:opacity-70 transition-opacity`} />
      <div className="relative flex items-start justify-between">
        <div className={`p-3 rounded-xl ${c.bg} ${c.border} border`}>
          <div className={c.text}>{icon}</div>
        </div>
        <span className={`text-xs font-medium px-2 py-1 rounded-full ${c.bg} ${c.text} border ${c.border}`}>
          {trend}
        </span>
      </div>
      <div className="relative mt-4">
        <p className="text-3xl font-bold text-slate-100">{displayValue}</p>
        <p className="text-sm text-slate-400 mt-1">{label}</p>
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