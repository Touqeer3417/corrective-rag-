import { useState, useRef, useEffect } from 'react';
import { Send, Loader2, BookOpen, ChevronDown, ChevronUp } from 'lucide-react';
import { streamMessage } from '../services/chat';
import { Citation } from '../types/document';

export default function ChatPage() {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [citations, setCitations] = useState<Citation[]>([]);
  const [loading, setLoading] = useState(false);
  const [expandedCitation, setExpandedCitation] = useState<string | null>(null);
  const [metadata, setMetadata] = useState<{ retry_count?: number; transformed_query?: string }>({});
  const abortRef = useRef<(() => void) | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [answer, citations]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || loading) return;
    setLoading(true);
    setAnswer('');
    setCitations([]);
    setExpandedCitation(null);
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

  const toggleCitation = (id: string) => {
    setExpandedCitation((prev) => (prev === id ? null : id));
  };

  return (
    <div className="max-w-4xl mx-auto h-[calc(100vh-4rem)] flex flex-col">
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Document Search</h2>
      
      <div className="flex-1 card mb-4 overflow-auto flex flex-col">
        {!answer && !loading && (
          <div className="flex-1 flex items-center justify-center text-gray-400">
            <div className="text-center">
              <BookOpen size={48} className="mx-auto mb-4 opacity-50" />
              <p>Ask a question about your company documents:</p>
            </div>
          </div>
        )}
        
        {/* ANSWER TEXT - YEH MAIN AREA HAI */}
        {answer && (
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">Answer</h3>
            <div className="whitespace-pre-wrap text-gray-800 leading-relaxed text-base">{answer}</div>
          </div>
        )}

        {/* SOURCES SECTION */}
        {citations.length > 0 && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            <h4 className="text-sm font-semibold text-gray-700 mb-3">Sources</h4>
            <div className="space-y-2">
              {citations.map((c) => (
                <div key={c.citation_id} className="border border-gray-200 rounded-lg overflow-hidden">
                  <button
                    onClick={() => toggleCitation(c.citation_id)}
                    className="w-full flex items-center justify-between px-4 py-2.5 bg-blue-50 hover:bg-blue-100 transition-colors text-left"
                  >
                    <span className="text-sm font-medium text-blue-800">
                      {c.document_name}, Page {c.page_number || 'N/A'}
                    </span>
                    {expandedCitation === c.citation_id ? (
                      <ChevronUp size={16} className="text-blue-600" />
                    ) : (
                      <ChevronDown size={16} className="text-blue-600" />
                    )}
                  </button>
                  
                  {/* EXPANDED CONTENT - YEH SCREEN PE DIKHEGA */}
                  {expandedCitation === c.citation_id && (
                    <div className="px-4 py-3 bg-gray-50 text-sm text-gray-700 leading-relaxed border-t border-gray-200">
                      <p className="font-medium text-gray-500 text-xs mb-1">Relevance Score: {(c.score * 100).toFixed(1)}%</p>
                      <p>{c.text}</p>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* QUERY REWRITE INFO */}
        {metadata.transformed_query && (
          <p className="mt-3 text-xs text-gray-400 italic">
            Rewritten query: {metadata.transformed_query}
          </p>
        )}

        <div ref={bottomRef} />
      </div>

      {/* INPUT AREA */}
      <form onSubmit={handleSubmit} className="flex gap-3">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="What is the company leave policy?"
          className="input flex-1"
          disabled={loading}
        />
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