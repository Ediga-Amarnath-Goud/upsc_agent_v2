import GlassCard from '../ui/GlassCard';
import CircularProgress from '../ui/CircularProgress';

export default function StudyHours() {
  return (
    <GlassCard className="flex items-center gap-4">
      <CircularProgress value={42} size={70} strokeWidth={5} color="#FF8A34" />
      <div>
        <div className="kpi-number text-accent-orange">10</div>
        <div className="text-sm text-text-secondary">Hrs Today</div>
      </div>
    </GlassCard>
  );
}
