import GlassCard from '../ui/GlassCard';
import KPINumber from '../ui/KPINumber';

export default function PendingPYQs() {
  return (
    <GlassCard className="flex flex-col justify-center">
      <KPINumber value={218} unit="" trend={12} trendUp={false} />
      <div className="text-sm text-text-secondary mt-1">Review Due</div>
    </GlassCard>
  );
}
