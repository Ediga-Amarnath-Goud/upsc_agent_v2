import GlassCard from '../ui/GlassCard';
import KPINumber from '../ui/KPINumber';

export default function BacklogsDue() {
  return (
    <GlassCard className="flex flex-col justify-center">
      <span className="text-5xl font-bold text-accent-red">4</span>
      <div className="text-sm text-accent-red/80 mt-1">Topics</div>
      <div className="text-xs text-text-secondary mt-0.5">Backlogs Due</div>
    </GlassCard>
  );
}
