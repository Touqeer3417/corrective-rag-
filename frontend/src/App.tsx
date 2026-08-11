import { Routes, Route, Link } from 'react-router-dom'
import { FileText, MessageSquare, LayoutDashboard, Upload } from 'lucide-react'
import Dashboard from './pages/Dashboard'
import DocumentLibrary from './pages/DocumentLibrary'
import UploadPage from './pages/UploadPage'
import ChatPage from './pages/ChatPage'

export default function App() {
  return (
    <div className="min-h-screen flex">
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-6 border-b border-gray-200">
          <h1 className="text-xl font-bold text-blue-900 flex items-center gap-2">
            <FileText size={24} />
            CRAG Search
          </h1>
        </div>
        <nav className="flex-1 p-4 space-y-2">
          <NavLink to="/" icon={<LayoutDashboard size={18} />}>Dashboard</NavLink>
          <NavLink to="/upload" icon={<Upload size={18} />}>Upload</NavLink>
          <NavLink to="/documents" icon={<FileText size={18} />}>Documents</NavLink>
          <NavLink to="/chat" icon={<MessageSquare size={18} />}>Chat</NavLink>
        </nav>
     
      </aside>
      <main className="flex-1 p-8 overflow-auto">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/documents" element={<DocumentLibrary />} />
          <Route path="/chat" element={<ChatPage />} />
        </Routes>
      </main>
    </div>
  )
}

function NavLink({ to, icon, children }: { to: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <Link to={to} className="flex items-center gap-3 px-4 py-2.5 rounded-lg text-gray-700 hover:bg-gray-100 transition-colors">
      {icon}
      <span className="font-medium">{children}</span>
    </Link>
  )
}
