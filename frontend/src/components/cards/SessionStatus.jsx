import GlassCard from '../ui/GlassCard';
import CircularProgress from '../ui/CircularProgress';

export default function SessionStatus() {
  return (
    <GlassCard gradient className="flex flex-col gap-3">
      <div className="text-sm font-medium text-white/70">Session Status</div>
      <div className="text-xs text-accent-blue font-medium">GS2 Polity</div>
      <div className="kpi-number text-white">02:45:18</div>
      <div className="flex items-center gap-4">
        <CircularProgress value={60} size={70} strokeWidth={5} color="#2D9CFF" />
        <span className="text-sm text-text-secondary">60% <br/>complete</span>
      </div>
      <div className="flex gap-2 mt-1">
        <button className="flex-1 py-2 rounded-lg bg-accent-red/20 text-accent-red text-sm font-medium hover:bg-accent-red/30 transition">Pause</button>
        <button className="flex-1 py-2 rounded-lg bg-white/5 text-text-secondary text-sm font-medium hover:bg-white/10 transition">End</button>
      </div>
    </GlassCard>
  );
}
