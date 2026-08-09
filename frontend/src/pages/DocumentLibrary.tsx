import { useEffect } from 'react';
import { Trash2, FileText } from 'lucide-react';
import { useDocumentStore } from '../stores/documentStore';
import { deleteDocument } from '../services/documents';

export default function DocumentLibrary() {
  const { documents, loading, fetchDocuments, removeDocument } = useDocumentStore();
  useEffect(() => { fetchDocuments(); }, []);

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this document?')) return;
    await deleteDocument(id);
    removeDocument(id);
  };

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Document Library</h2>
      <div className="card overflow-hidden">
        <table className="w-full text-left">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-6 py-3 text-xs font-semibold text-gray-500 uppercase">Name</th>
              <th className="px-6 py-3 text-xs font-semibold text-gray-500 uppercase">Type</th>
              <th className="px-6 py-3 text-xs font-semibold text-gray-500 uppercase">Chunks</th>
              <th className="px-6 py-3 text-xs font-semibold text-gray-500 uppercase">Status</th>
              <th className="px-6 py-3 text-xs font-semibold text-gray-500 uppercase"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {documents.map((doc) => (
              <tr key={doc.document_id} className="hover:bg-gray-50">
                <td className="px-6 py-4">
                  <div className="flex items-center gap-3">
                    <FileText size={18} className="text-gray-400" />
                    <span className="font-medium text-gray-900">{doc.original_name}</span>
                  </div>
                </td>
                <td className="px-6 py-4 text-sm text-gray-600 uppercase">{doc.file_type}</td>
                <td className="px-6 py-4 text-sm text-gray-600">{doc.chunk_count}</td>
                <td className="px-6 py-4">
                  <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${
                    doc.status === 'indexed' ? 'bg-green-100 text-green-800' :
                    doc.status === 'error' ? 'bg-red-100 text-red-800' :
                    'bg-yellow-100 text-yellow-800'
                  }`}>{doc.status}</span>
                </td>
                <td className="px-6 py-4">
                  <button onClick={() => handleDelete(doc.document_id)} className="text-red-600 hover:text-red-800">
                    <Trash2 size={18} />
                  </button>
                </td>
              </tr>
            ))}
            {documents.length === 0 && !loading && (
              <tr><td colSpan={5} className="px-6 py-8 text-center text-gray-500">No documents found</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
