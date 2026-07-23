import GlassCard from '../ui/GlassCard';

export default function ActiveSession() {
  return (
    <GlassCard gradient className="flex flex-col gap-3">
      <div className="text-sm font-medium text-white/70">Active Session</div>
      <div className="kpi-number text-white">1:02:45</div>
      <div>
        <span className="inline-block px-2.5 py-0.5 rounded-full bg-accent-green/20 text-accent-green text-xs font-medium">ACTIVE</span>
      </div>
      <div className="w-full h-1.5 bg-white/10 rounded-full overflow-hidden mt-1">
        <div className="h-full w-3/5 bg-accent-blue rounded-full" />
      </div>
      <div className="flex gap-2 mt-2">
        <button className="flex-1 py-2 rounded-lg bg-accent-red/20 text-accent-red text-sm font-medium hover:bg-accent-red/30 transition">Pause</button>
        <button className="flex-1 py-2 rounded-lg bg-white/5 text-text-secondary text-sm font-medium hover:bg-white/10 transition">End</button>
      </div>
    </GlassCard>
  );
}
