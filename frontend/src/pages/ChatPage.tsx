import { useState, useRef, useEffect } from 'react';
import { Send, Loader2, BookOpen, ChevronDown, ChevronUp, Sparkles, Zap, Brain, Clock } from 'lucide-react';
import { streamMessage } from '../services/chat';
import { Citation } from '../services/chat';

export default function ChatPage() {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [citations, setCitations] = useState<Citation[]>([]);
  const [loading, setLoading] = useState(false);
  const [expandedCitation, setExpandedCitation] = useState<string | null>(null);
  const [metadata, setMetadata] = useState<{ retry_count?: number; transformed_query?: string }>({});
  const [isTyping, setIsTyping] = useState(false);
  const [responseTime, setResponseTime] = useState<number | null>(null);
  const abortRef = useRef<(() => void) | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const startTimeRef = useRef<number>(0);

  
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [answer, citations]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || loading) return;
    setLoading(true);
    setIsTyping(true);
    setAnswer('');
    setCitations([]);
    setExpandedCitation(null);
    setMetadata({});
    setResponseTime(null);
    startTimeRef.current = Date.now();

    abortRef.current = streamMessage(
      question,
      (token) => {
        setAnswer((prev) => prev + token);
        setIsTyping(false);
      },
      (citation) => setCitations((prev) => [...prev, citation]),
      () => {
        const duration = (Date.now() - startTimeRef.current) / 1000;
        setResponseTime(duration);
        setLoading(false);
        setIsTyping(false);
      },
      (m) => setMetadata(m),
    );
  };

  const handleStop = () => {
    abortRef.current?.();
    if (startTimeRef.current > 0) {
      const duration = (Date.now() - startTimeRef.current) / 1000;
      setResponseTime(duration);
    }
    setLoading(false);
    setIsTyping(false);
  };

  const toggleCitation = (id: string) => {
    setExpandedCitation((prev) => (prev === id ? null : id));
  };

  const topCitation = citations[0] || null;

  return (
    <div className="max-w-4xl mx-auto h-[calc(100vh-4rem)] flex flex-col px-4 py-6">
      {/* Header */}
      <div className="mb-6 flex items-center gap-3">
        <div className="relative">
          <div className="absolute inset-0 bg-cyan-500/20 blur-xl rounded-full" />
          <Brain className="relative w-8 h-8 text-cyan-400" />
        </div>
        <div>
          <h2 className="text-2xl font-bold bg-gradient-to-r from-cyan-400 via-violet-400 to-emerald-400 bg-clip-text text-transparent">
            Document Search
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">Ask anything about your documents</p>
        </div>
      </div>

      {/* Chat Area */}
      <div
        ref={chatContainerRef}
        className="flex-1 relative mb-4 overflow-hidden rounded-2xl border border-slate-700/50 bg-slate-900/40 backdrop-blur-xl"
      >
        {/* Subtle grid pattern overlay */}
        <div className="absolute inset-0 opacity-[0.03]" style={{
          backgroundImage: `radial-gradient(circle at 1px 1px, rgba(148,163,184,1) 1px, transparent 0)`,
          backgroundSize: '24px 24px'
        }} />

        <div className="relative h-full overflow-y-auto p-6 space-y-6 custom-scrollbar">
          {/* Empty State */}
          {!answer && !loading && (
            <div className="flex-1 flex items-center justify-center min-h-[400px]">
              <div className="text-center space-y-4">
                <div className="relative inline-block">
                  <div className="absolute inset-0 bg-cyan-500/10 blur-2xl rounded-full animate-pulse" />
                  <BookOpen size={56} className="relative text-slate-600 mx-auto" />
                </div>
                <div>
                  <p className="text-slate-400 text-lg font-medium">Ready to search your documents</p>
                  <p className="text-slate-500 text-sm mt-1">Ask a question and I&apos;ll find the answer from your knowledge base</p>
                </div>
                <div className="flex gap-2 justify-center mt-4">
                  {['What is the leave policy?', 'Company handbook summary', 'IT guidelines'].map((suggestion) => (
                    <button
                      key={suggestion}
                      onClick={() => setQuestion(suggestion)}
                      className="px-3 py-1.5 text-xs rounded-full border border-slate-700/60 bg-slate-800/50 text-slate-400 hover:text-cyan-400 hover:border-cyan-500/30 hover:bg-cyan-500/5 transition-all duration-300"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Question Bubble */}
          {question && (answer || loading) && (
            <div className="flex justify-end animate-in slide-in-from-right-4 duration-300">
              <div className="max-w-[80%] rounded-2xl rounded-tr-sm px-5 py-3 bg-gradient-to-br from-cyan-500/20 to-violet-500/20 border border-cyan-500/20 backdrop-blur-sm">
                <p className="text-slate-100 text-sm leading-relaxed">{question}</p>
              </div>
            </div>
          )}

          {/* Answer Section */}
          {answer && (
            <div className="animate-in slide-in-from-bottom-4 duration-500 space-y-4">
              <div className="flex items-center gap-2 mb-2">
                <Sparkles size={14} className="text-violet-400" />
                <span className="text-xs font-semibold text-violet-400 uppercase tracking-wider">Answer</span>
                {responseTime !== null && (
                  <span className="ml-auto flex items-center gap-1 text-[10px] font-medium text-slate-400 bg-slate-800/60 border border-slate-700/40 px-2 py-0.5 rounded-full">
                    <Clock size={10} />
                    {responseTime.toFixed(2)}s
                  </span>
                )}
              </div>
              <div className="rounded-2xl border border-slate-700/40 bg-slate-800/30 backdrop-blur-sm p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
                <div className="whitespace-pre-wrap text-slate-200 leading-relaxed text-[15px]">
                  {answer}
                  {isTyping && (
                    <span className="inline-block w-1.5 h-4 ml-0.5 bg-cyan-400 animate-pulse rounded-sm" />
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Loading State (before answer) */}
          {loading && !answer && (
            <div className="flex items-center gap-3 text-slate-500 animate-pulse">
              <div className="w-2 h-2 bg-cyan-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <div className="w-2 h-2 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <div className="w-2 h-2 bg-emerald-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              <span className="text-sm ml-2">Searching documents...</span>
            </div>
          )}

          {/* Source Citation */}
          {topCitation && (
            <div className="animate-in slide-in-from-bottom-4 duration-500 delay-100">
              <div className="flex items-center gap-2 mb-3">
                <Zap size={14} className="text-amber-400" />
                <span className="text-xs font-semibold text-amber-400 uppercase tracking-wider">Source</span>
              </div>

              <div className="rounded-xl border border-slate-700/40 bg-slate-800/30 backdrop-blur-sm overflow-hidden shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
                <button
                  onClick={() => toggleCitation(topCitation.citation_id)}
                  className="w-full flex items-center justify-between px-5 py-4 hover:bg-slate-700/20 transition-all duration-300 group"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/20">
                      <BookOpen size={16} className="text-amber-400" />
                    </div>
                    <div className="text-left">
                      <span className="text-sm font-medium text-slate-200 group-hover:text-amber-300 transition-colors">
                        {topCitation.document_name}
                      </span>
                      <span className="text-slate-500 text-sm ml-2">· Page {topCitation.page_number || 'N/A'}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2.5 py-1 rounded-full">
                      {(topCitation.score * 100).toFixed(1)}% match
                    </span>
                    {expandedCitation === topCitation.citation_id ? (
                      <ChevronUp size={16} className="text-slate-400" />
                    ) : (
                      <ChevronDown size={16} className="text-slate-400" />
                    )}
                  </div>
                </button>

                {expandedCitation === topCitation.citation_id && (
                  <div className="px-5 py-4 border-t border-slate-700/40 bg-slate-800/20 animate-in slide-in-from-top-2 duration-200">
                    <p className="text-sm text-slate-300 leading-relaxed italic border-l-2 border-amber-500/40 pl-4">
                      &ldquo;{topCitation.text}&rdquo;
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Metadata */}
         

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input Area */}
      <form onSubmit={handleSubmit} className="relative group">
        <div className="absolute -inset-0.5 bg-gradient-to-r from-cyan-500/20 via-violet-500/20 to-emerald-500/20 rounded-2xl blur opacity-0 group-focus-within:opacity-100 transition duration-500" />
        <div className="relative flex gap-3 p-2 rounded-2xl border border-slate-700/60 bg-slate-900/80 backdrop-blur-xl shadow-2xl">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="What is the company leave policy?"
            className="flex-1 bg-transparent text-slate-100 placeholder-slate-500 px-4 py-3 text-sm outline-none border-none focus:ring-0"
            disabled={loading}
          />
          {loading ? (
            <button
              type="button"
              onClick={handleStop}
              className="px-5 py-2.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 transition-all duration-300 flex items-center gap-2 text-sm font-medium"
            >
              <Loader2 className="animate-spin" size={16} /> Stop
            </button>
          ) : (
            <button
              type="submit"
              disabled={!question.trim()}
              className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-violet-500 text-white hover:shadow-[0_0_20px_rgba(6,182,212,0.3)] hover:scale-[1.02] active:scale-[0.98] transition-all duration-300 flex items-center gap-2 text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:scale-100 disabled:hover:shadow-none"
            >
              <Send size={16} /> Ask
            </button>
          )}
        </div>
      </form>
    </div>
  );
}