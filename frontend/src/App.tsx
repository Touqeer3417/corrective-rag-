import { useState, useEffect } from 'react';
import { Routes, Route, Link, useLocation } from 'react-router-dom';
import {
  FileText,
  MessageSquare,
  LayoutDashboard,
  Upload,
  Brain,
  Activity,
  ChevronRight
} from 'lucide-react';
import Dashboard from './pages/Dashboard';
import DocumentLibrary from './pages/DocumentLibrary';
import UploadPage from './pages/UploadPage';
import ChatPage from './pages/ChatPage';
import SplashScreen from './components/SplashScreen.tsx';

export default function App() {
  const [showSplash, setShowSplash] = useState(false);
  const location = useLocation();

  // Check if splash should show (once per session)
  useEffect(() => {
    const hasSeenSplash = sessionStorage.getItem('crag-splash-seen');
    if (!hasSeenSplash) {
      setShowSplash(true);
    }
  }, []);

  const handleSplashComplete = () => {
    sessionStorage.setItem('crag-splash-seen', 'true');
    setShowSplash(false);
  };

  const navItems = [
    { path: '/', label: 'Dashboard', icon: LayoutDashboard },
    { path: '/upload', label: 'Upload', icon: Upload },
    { path: '/documents', label: 'Documents', icon: FileText },
    { path: '/chat', label: 'Chat', icon: MessageSquare },
  ];

  return (
    <>
      {/* Splash Animation */}
      {showSplash && <SplashScreen onComplete={handleSplashComplete} />}

      <div className="min-h-screen bg-slate-950 text-slate-100 flex">
        {/* Sidebar */}
        <aside className="w-64 border-r border-slate-800/60 bg-slate-900/80 backdrop-blur-xl flex flex-col">
          {/* Logo */}
          <div className="p-6 border-b border-slate-800/60">
            <div className="flex items-center gap-3">
              <div className="relative">
                <div className="absolute inset-0 bg-cyan-500/20 blur-lg rounded-full" />
                <Brain className="relative w-8 h-8 text-cyan-400" />
              </div>
              <div>
                <h1 className="text-lg font-bold bg-gradient-to-r from-cyan-400 to-violet-400 bg-clip-text text-transparent">
                  CRAG Search
                </h1>
                <p className="text-[10px] text-slate-500 uppercase tracking-widest">Knowledge Base</p>
              </div>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex-1 p-4 space-y-1">
            {navItems.map((item) => {
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-300 group ${
                    isActive
                      ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 shadow-[0_0_15px_rgba(6,182,212,0.1)]'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 border border-transparent'
                  }`}
                >
                  <item.icon size={18} className="transition-transform group-hover:scale-110" />
                  <span>{item.label}</span>
                  {isActive && <ChevronRight size={14} className="ml-auto text-cyan-400/60" />}
                </Link>
              );
            })}
          </nav>

          {/* Footer */}
        
        </aside>

        {/* Main Content */}
        <main className="flex-1 overflow-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/documents" element={<DocumentLibrary />} />
            <Route path="/chat" element={<ChatPage />} />
          </Routes>
        </main>
      </div>
    </>
  );
}