import GlassCard from '../ui/GlassCard';
import CircularProgress from '../ui/CircularProgress';

export default function TodaysMission() {
  return (
    <GlassCard className="flex flex-col gap-3">
      <div className="text-sm font-medium text-white/70">Today's Mission</div>
      <div className="text-xs text-accent-blue font-medium">GS3 Economy: Budget & Fiscal</div>
      <div className="space-y-1.5 text-sm">
        <div className="flex items-center gap-2"><span className="text-accent-green">✓</span> <span className="text-text-secondary">Tax revenue trends</span></div>
        <div className="flex items-center gap-2"><span className="text-white/30">○</span> <span className="text-text-secondary">Fiscal deficit targets</span></div>
        <div className="flex items-center gap-2"><span className="text-white/30">○</span> <span className="text-text-secondary">GST compensation</span></div>
      </div>
      <div className="flex items-center justify-between mt-1">
        <span className="text-xs text-text-secondary">42 Tasks</span>
        <div className="flex items-center gap-2">
          <CircularProgress value={35} size={44} strokeWidth={4} color="#FF8A34" />
          <span className="text-sm font-semibold text-accent-orange">3.5 Hrs Left</span>
        </div>
      </div>
    </GlassCard>
  );
}
