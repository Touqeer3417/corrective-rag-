import {
  useCallback,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
} from 'react';

import {
  CheckCircle,
  File,
  FileType2,
  Loader2,
  UploadCloud,
  X,
  XCircle,
} from 'lucide-react';

import { uploadDocument } from '../services/documents';
import { useDocumentStore } from '../stores/documentStore';

type UploadResult = {
  name: string;
  status: 'success' | 'error';
  message: string;
};

function getUploadErrorMessage(error: any): string {
  const detail = error?.response?.data?.detail;

  if (typeof detail === 'string') {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item: any) => {
        if (typeof item === 'string') {
          return item;
        }

        if (item?.msg) {
          return item.msg;
        }

        try {
          return JSON.stringify(item);
        } catch {
          return 'Unknown validation error';
        }
      })
      .join(', ');
  }

  if (detail && typeof detail === 'object') {
    try {
      return JSON.stringify(detail);
    } catch {
      return 'Upload failed due to a server validation error.';
    }
  }

  if (error?.response?.data?.message) {
    return String(error.response.data.message);
  }

  if (error?.message) {
    return String(error.message);
  }

  return 'Upload failed. Please try again.';
}

export default function UploadPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [results, setResults] = useState<UploadResult[]>([]);

  const fetchDocuments = useDocumentStore((state) => state.fetchDocuments);

  const inputRef = useRef<HTMLInputElement>(null);

  const onDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragActive(false);

    const droppedFiles = Array.from(e.dataTransfer.files);

    if (droppedFiles.length > 0) {
      setFiles((prev) => [...prev, ...droppedFiles]);
    }
  }, []);

  const onDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragActive(true);
  }, []);

  const onDragLeave = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragActive(false);
  }, []);

  const onFileSelect = (e: ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;

    const selectedFiles = Array.from(e.target.files);

    if (selectedFiles.length > 0) {
      setFiles((prev) => [...prev, ...selectedFiles]);
    }

    // Allows selecting the same file again later
    e.target.value = '';
  };

  const removeFile = (index: number) => {
    if (uploading) return;

    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (files.length === 0 || uploading) return;

    setUploading(true);
    setResults([]);

    let atLeastOneUploadSucceeded = false;

    try {
      for (const file of files) {
        try {
          console.log(`Uploading file: ${file.name}`);

          await uploadDocument(file);

          atLeastOneUploadSucceeded = true;

          setResults((prev) => [
            ...prev,
            {
              name: file.name,
              status: 'success',
              message: 'Uploaded & indexed successfully',
            },
          ]);

          console.log(`Upload successful: ${file.name}`);
        } catch (error: any) {
          console.error(`Upload failed: ${file.name}`, error);

          const errorMessage = getUploadErrorMessage(error);

          setResults((prev) => [
            ...prev,
            {
              name: file.name,
              status: 'error',
              message: errorMessage,
            },
          ]);
        }
      }

      // Refresh document list from backend instead of manually inserting
      // an upload response with a different object shape.
      if (atLeastOneUploadSucceeded) {
        try {
          await fetchDocuments();
        } catch (error) {
          console.error('Failed to refresh document list:', error);
        }
      }
    } finally {
      setUploading(false);
      setFiles([]);
    }
  };

  const totalSize = files.reduce((acc, file) => acc + file.size, 0);

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="text-center mb-8">
        <div className="relative inline-block mb-4">
          <div className="absolute inset-0 bg-cyan-500/20 blur-2xl rounded-full animate-pulse" />

          <UploadCloud
            size={48}
            className="relative text-cyan-400"
          />
        </div>

        <h2 className="text-3xl font-bold bg-gradient-to-r from-cyan-400 via-violet-400 to-emerald-400 bg-clip-text text-transparent">
          Upload Documents
        </h2>

        <p className="text-slate-400 text-sm mt-2 max-w-md mx-auto">
          Drag and drop your files or click to browse. We support PDF,
          DOCX, TXT, and MD.
        </p>
      </div>

      {/* Dropzone */}
      <div
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onClick={() => {
          if (!uploading) {
            inputRef.current?.click();
          }
        }}
        className={`relative rounded-2xl border-2 border-dashed p-12 text-center transition-all duration-500 group overflow-hidden ${
          uploading
            ? 'cursor-not-allowed opacity-70'
            : 'cursor-pointer'
        } ${
          dragActive
            ? 'border-cyan-400 bg-cyan-500/5 shadow-[0_0_30px_rgba(6,182,212,0.15)]'
            : 'border-slate-700/50 bg-slate-900/40 hover:border-slate-600 hover:bg-slate-800/30'
        }`}
      >
        {dragActive && (
          <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/10 via-violet-500/10 to-emerald-500/10 animate-pulse" />
        )}

        <div className="relative">
          <div
            className={`mx-auto w-16 h-16 rounded-2xl flex items-center justify-center mb-4 transition-all duration-300 ${
              dragActive
                ? 'bg-cyan-500/20 scale-110'
                : 'bg-slate-800/50 border border-slate-700/40 group-hover:border-cyan-500/20 group-hover:bg-cyan-500/5'
            }`}
          >
            <UploadCloud
              size={28}
              className={`transition-colors ${
                dragActive
                  ? 'text-cyan-400'
                  : 'text-slate-500 group-hover:text-cyan-400'
              }`}
            />
          </div>

          <p
            className={`text-base font-medium transition-colors ${
              dragActive ? 'text-cyan-400' : 'text-slate-300'
            }`}
          >
            {dragActive ? 'Drop files here!' : 'Drag & drop files here'}
          </p>

          <p className="text-sm text-slate-500 mt-1">
            or click to browse from your computer
          </p>
        </div>

        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".pdf,.docx,.txt,.md"
          onChange={onFileSelect}
          disabled={uploading}
          className="hidden"
        />
      </div>

      {/* Selected Files */}
      {files.length > 0 && (
        <div className="rounded-2xl border border-slate-700/50 bg-slate-900/40 backdrop-blur-xl overflow-hidden shadow-[0_0_40px_rgba(0,0,0,0.2)] animate-in slide-in-from-bottom-4 duration-300">
          <div className="px-6 py-4 border-b border-slate-700/40 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <FileType2
                size={18}
                className="text-violet-400"
              />

              <h3 className="font-semibold text-slate-200">
                Selected Files ({files.length})
              </h3>
            </div>

            <span className="text-xs text-slate-500">
              {(totalSize / 1024 / 1024).toFixed(2)} MB total
            </span>
          </div>

          <div className="p-4 space-y-2 max-h-64 overflow-y-auto custom-scrollbar">
            {files.map((file, index) => (
              <div
                key={`${file.name}-${file.size}-${index}`}
                className="flex items-center justify-between p-3 rounded-xl bg-slate-800/30 border border-slate-700/30 hover:border-slate-600 transition-all group"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="p-2 rounded-lg bg-slate-700/30 shrink-0">
                    <File
                      size={16}
                      className="text-cyan-400"
                    />
                  </div>

                  <div className="min-w-0">
                    <p className="text-sm font-medium text-slate-200 truncate">
                      {file.name}
                    </p>

                    <p className="text-xs text-slate-500">
                      {(file.size / 1024).toFixed(1)} KB ·{' '}
                      {file.type || 'Unknown type'}
                    </p>
                  </div>
                </div>

                <button
                  type="button"
                  disabled={uploading}
                  onClick={(e) => {
                    e.stopPropagation();
                    removeFile(index);
                  }}
                  aria-label={`Remove ${file.name}`}
                  className="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition-all opacity-0 group-hover:opacity-100 disabled:cursor-not-allowed disabled:opacity-30"
                >
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>

          <div className="px-6 py-4 border-t border-slate-700/40">
            <button
              type="button"
              onClick={handleUpload}
              disabled={uploading}
              className="w-full py-3 rounded-xl bg-gradient-to-r from-cyan-500 to-violet-500 text-white font-medium hover:shadow-[0_0_25px_rgba(6,182,212,0.3)] hover:scale-[1.01] active:scale-[0.99] transition-all duration-300 flex justify-center items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
            >
              {uploading && (
                <Loader2
                  className="animate-spin"
                  size={18}
                />
              )}

              {uploading
                ? 'Uploading & Indexing...'
                : `Upload ${files.length} File${
                    files.length > 1 ? 's' : ''
                  }`}
            </button>
          </div>
        </div>
      )}

      {/* Results */}
      {results.length > 0 && (
        <div className="space-y-3 animate-in slide-in-from-bottom-4 duration-500">
          <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
            Upload Results
          </h3>

          {results.map((result, index) => (
            <div
              key={`${result.name}-${index}`}
              className={`rounded-xl border p-4 flex items-center gap-4 transition-all duration-300 ${
                result.status === 'success'
                  ? 'border-emerald-500/20 bg-emerald-500/5 hover:bg-emerald-500/10'
                  : 'border-rose-500/20 bg-rose-500/5 hover:bg-rose-500/10'
              }`}
            >
              <div
                className={`p-2 rounded-lg ${
                  result.status === 'success'
                    ? 'bg-emerald-500/10'
                    : 'bg-rose-500/10'
                }`}
              >
                {result.status === 'success' ? (
                  <CheckCircle
                    size={20}
                    className="text-emerald-400"
                  />
                ) : (
                  <XCircle
                    size={20}
                    className="text-rose-400"
                  />
                )}
              </div>

              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-200 truncate">
                  {result.name}
                </p>

                <p
                  className={`text-xs mt-0.5 break-words ${
                    result.status === 'success'
                      ? 'text-emerald-400/80'
                      : 'text-rose-400/80'
                  }`}
                >
                  {result.message}
                </p>
              </div>

              <span
                className={`text-xs font-medium px-2.5 py-1 rounded-full shrink-0 ${
                  result.status === 'success'
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                    : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                }`}
              >
                {result.status === 'success' ? 'Success' : 'Failed'}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}