import { useState, useCallback } from 'react';
import { UploadCloud, CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { uploadDocument } from '../services/documents';
import { useDocumentStore } from '../stores/documentStore';

export default function UploadPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [results, setResults] = useState<{ name: string; status: 'success' | 'error'; message: string }[]>([]);
  const addDocument = useDocumentStore((s) => s.addDocument);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setFiles((prev) => [...prev, ...Array.from(e.dataTransfer.files)]);
  }, []);

  const onFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) setFiles((prev) => [...prev, ...Array.from(e.target.files)]);
  };

  const handleUpload = async () => {
    setUploading(true);
    setResults([]);
    for (const file of files) {
      try {
        const res = await uploadDocument(file);
        setResults((prev) => [...prev, { name: file.name, status: 'success', message: 'Uploaded successfully' }]);
        if (res.data) addDocument(res.data);
      } catch (e: any) {
        setResults((prev) => [...prev, { name: file.name, status: 'error', message: e.response?.data?.detail || 'Upload failed' }]);
      }
    }
    setUploading(false);
    setFiles([]);
  };

  return (
    <div className="max-w-2xl space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Upload Documents</h2>
      <div
        onDrop={onDrop}
        onDragOver={(e) => e.preventDefault()}
        className="border-2 border-dashed border-gray-300 rounded-xl p-12 text-center hover:border-blue-500 transition-colors bg-white"
      >
        <UploadCloud className="mx-auto h-12 w-12 text-gray-400 mb-4" />
        <p className="text-gray-600 mb-2">Drag and drop files here, or click to browse</p>
        <input type="file" multiple onChange={onFileSelect} className="hidden" id="file-input" />
        <label htmlFor="file-input" className="btn-primary cursor-pointer inline-block">Select Files</label>
      </div>

      {files.length > 0 && (
        <div className="card">
          <h3 className="font-semibold mb-3">Selected Files ({files.length})</h3>
          <ul className="space-y-2 mb-4">
            {files.map((f, i) => (
              <li key={i} className="flex justify-between text-sm text-gray-700">
                <span>{f.name}</span>
                <span className="text-gray-400">{(f.size / 1024).toFixed(1)} KB</span>
              </li>
            ))}
          </ul>
          <button onClick={handleUpload} disabled={uploading} className="btn-primary w-full flex justify-center items-center gap-2">
            {uploading && <Loader2 className="animate-spin" size={18} />}
            {uploading ? 'Uploading...' : 'Upload All'}
          </button>
        </div>
      )}

      {results.length > 0 && (
        <div className="space-y-2">
          {results.map((r, i) => (
            <div key={i} className={`card py-3 flex items-center gap-3 ${r.status === 'success' ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'}`}>
              {r.status === 'success' ? <CheckCircle size={18} className="text-green-600" /> : <XCircle size={18} className="text-red-600" />}
              <div>
                <p className="font-medium text-sm">{r.name}</p>
                <p className="text-xs text-gray-600">{r.message}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
