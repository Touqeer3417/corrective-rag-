import { useEffect } from 'react';
import { FileText, CheckCircle, Clock, AlertCircle } from 'lucide-react';
import { useDocumentStore } from '../stores/documentStore';

export default function Dashboard() {
  const { documents, fetchDocuments } = useDocumentStore();
  useEffect(() => { fetchDocuments(); }, []);

  const total = documents.length;
  const indexed = documents.filter((d) => d.status === 'indexed').length;
  const pending = documents.filter((d) => d.status === 'pending' || d.status === 'processing').length;
  const errors = documents.filter((d) => d.status === 'error').length;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <StatCard icon={<FileText className="text-blue-600" />} label="Total Documents" value={total} />
        <StatCard icon={<CheckCircle className="text-green-600" />} label="Indexed" value={indexed} />
        <StatCard icon={<Clock className="text-yellow-600" />} label="Pending" value={pending} />
        <StatCard icon={<AlertCircle className="text-red-600" />} label="Errors" value={errors} />
      </div>
      <div className="card">
        <h3 className="text-lg font-semibold mb-4">Recent Uploads</h3>
        {documents.length === 0 ? (
          <p className="text-gray-500">No documents uploaded yet.</p>
        ) : (
          <div className="divide-y divide-gray-100">
            {documents.slice(0, 5).map((doc) => (
              <div key={doc.document_id} className="py-3 flex justify-between items-center">
                <div>
                  <p className="font-medium text-gray-900">{doc.original_name}</p>
                  <p className="text-sm text-gray-500">{doc.file_type.toUpperCase()} • {doc.chunk_count} chunks</p>
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

function StatCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: number }) {
  return (
    <div className="card flex items-center gap-4">
      <div className="p-3 bg-gray-100 rounded-lg">{icon}</div>
      <div>
        <p className="text-2xl font-bold text-gray-900">{value}</p>
        <p className="text-sm text-gray-500">{label}</p>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    indexed: 'bg-green-100 text-green-800',
    pending: 'bg-gray-100 text-gray-800',
    processing: 'bg-yellow-100 text-yellow-800',
    error: 'bg-red-100 text-red-800',
  };
  return (
    <span className={`px-3 py-1 rounded-full text-xs font-medium ${styles[status] || styles.pending}`}>
      {status}
    </span>
  );
}
