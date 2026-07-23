import { NavLink } from 'react-router-dom';

const NAV_ITEMS = [
  { label: 'Dashboard', path: '/', icon: '📊' },

  { label: 'Generate Test', path: '/generate-test', icon: '📝' },
  { label: 'My Tests', path: '/my-tests', icon: '📋' },
  { label: 'Current Affairs', path: '/current-affairs', icon: '📰' },
  { label: 'Profile Analysis', path: '/profile-analysis', icon: '📊' },
  { label: 'Upload PDF', path: '/upload', icon: '📄' },
  { label: 'Submit OMR', path: '/submit-omr', icon: '📷' },
  { label: 'Mains OCR', path: '/mains-ocr', icon: '📝' },
  { label: 'Active Session', path: '/session', icon: '⏱️' },
];

const BOTTOM_ITEMS = [
  { label: 'Logs', path: '/logs', icon: '📜' },
];

export default function Sidebar() {
  const linkClass = ({ isActive }) =>
    `flex items-center gap-3 px-5 py-4 text-sm font-medium transition-all rounded-xl mx-2 ${
      isActive
        ? 'bg-accent-blue/10 text-accent-blue border-l-2 border-accent-blue'
        : 'text-text-secondary hover:text-white hover:bg-white/5'
    }`;

  return (
    <aside className="w-[260px] min-h-screen bg-[#111111] flex flex-col border-r border-white/5 shrink-0">
      <div className="px-5 pt-6 pb-8">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-accent-blue flex items-center justify-center text-sm font-bold">U</div>
          <div>
            <div className="text-sm font-semibold text-white">UPSC Adaptive</div>
            <div className="text-xs text-text-secondary">AI Orchestrator</div>
          </div>
        </div>
      </div>

      <nav className="flex-1 flex flex-col gap-1">
        {NAV_ITEMS.map(item => (
          <NavLink key={item.label} to={item.path} end={item.path === '/'} className={linkClass}>
            <span className="text-lg">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-white/5 pt-2 pb-4">
        {BOTTOM_ITEMS.map(item => (
          <NavLink key={item.label} to={item.path} end className={linkClass}>
            <span className="text-lg">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </div>
    </aside>
  );
}
