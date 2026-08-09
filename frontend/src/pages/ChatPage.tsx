import { useState, useRef, useEffect } from 'react';
import { Send, Loader2, BookOpen } from 'lucide-react';
import { streamMessage } from '../services/chat';
import { Citation } from '../types/document';

export default function ChatPage() {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [citations, setCitations] = useState<Citation[]>([]);
  const [loading, setLoading] = useState(false);
  const [metadata, setMetadata] = useState<{ retry_count?: number; transformed_query?: string }>({});
  const abortRef = useRef<(() => void) | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [answer]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || loading) return;
    setLoading(true);
    setAnswer('');
    setCitations([]);
    setMetadata({});

    abortRef.current = streamMessage(
      question,
      (token) => setAnswer((prev) => prev + token),
      (citation) => setCitations((prev) => [...prev, citation]),
      () => setLoading(false),
      (m) => setMetadata(m),
    );
  };

  const handleStop = () => { abortRef.current?.(); setLoading(false); };

  return (
    <div className="max-w-4xl mx-auto h-[calc(100vh-4rem)] flex flex-col">
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Document Search</h2>
      <div className="flex-1 card mb-4 overflow-auto flex flex-col">
        {!answer && !loading && (
          <div className="flex-1 flex items-center justify-center text-gray-400">
            <div className="text-center">
              <BookOpen size={48} className="mx-auto mb-4 opacity-50" />
              <p>Ask a question about your company documents</p>
            </div>
          </div>
        )}
        {answer && <div className="whitespace-pre-wrap text-gray-800 leading-relaxed">{answer}</div>}
        {citations.length > 0 && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            <h4 className="text-sm font-semibold text-gray-700 mb-2">Sources</h4>
            <div className="flex flex-wrap gap-2">
              {citations.map((c) => (
                <button key={c.citation_id} onClick={() => alert(c.text)}
                  className="px-3 py-1.5 bg-blue-50 text-blue-700 text-xs font-medium rounded-lg hover:bg-blue-100 transition-colors"
                  title={c.text}>
                  {c.document_name}, Page {c.page_number || 'N/A'}
                </button>
              ))}
            </div>
          </div>
        )}
        {metadata.transformed_query && (
          <p className="mt-2 text-xs text-gray-400">Rewritten query: {metadata.transformed_query}</p>
        )}
        <div ref={bottomRef} />
      </div>
      <form onSubmit={handleSubmit} className="flex gap-3">
        <input value={question} onChange={(e) => setQuestion(e.target.value)}
          placeholder="What is the company leave policy?" className="input flex-1" disabled={loading} />
        {loading ? (
          <button type="button" onClick={handleStop} className="btn-secondary flex items-center gap-2">
            <Loader2 className="animate-spin" size={18} /> Stop
          </button>
        ) : (
          <button type="submit" className="btn-primary flex items-center gap-2">
            <Send size={18} /> Ask
          </button>
        )}
      </form>
    </div>
  );
}
