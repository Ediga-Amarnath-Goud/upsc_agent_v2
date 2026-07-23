import { useNavigate } from 'react-router-dom';
import GlassCard from '../ui/GlassCard';

export default function QuickActions() {
  const navigate = useNavigate();

  return (
    <GlassCard className="flex flex-col gap-2">
      <div className="text-sm font-medium text-white/70 mb-1">Quick Actions</div>
      <button onClick={() => navigate('/generate-test')} className="py-3 rounded-xl bg-accent-blue/20 text-accent-blue text-sm font-medium hover:bg-accent-blue/30 transition text-left px-4">
        🧪 Generate Test
      </button>
      <button className="py-3 rounded-xl bg-white/5 text-text-secondary text-sm font-medium hover:bg-white/10 transition text-left px-4">
        ▶ Resume Session
      </button>
      <button className="py-3 rounded-xl bg-white/5 text-text-secondary text-sm font-medium hover:bg-white/10 transition text-left px-4">
        📤 Upload Answer
      </button>
      <button className="py-3 rounded-xl bg-white/5 text-text-secondary text-sm font-medium hover:bg-white/10 transition text-left px-4">
        📄 Export PDFs
      </button>
    </GlassCard>
  );
}
