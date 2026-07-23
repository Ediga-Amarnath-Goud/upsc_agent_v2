import GlassCard from '../ui/GlassCard';
import StatusBadge from '../ui/StatusBadge';
import { useActivityLogs } from '../../hooks/useQueries';
import { timeAgo } from '../../utils/format';

const FALLBACK = [
  { label: 'Test', color: 'blue', title: 'Generated Test (GS3, #734)', meta: '10:05 AM' },
  { label: 'Essay', color: 'yellow', title: 'Mains Evaluator Essay', meta: '68/100 · 09:42 AM' },
  { label: 'OCR', color: 'green', title: 'OCR Notes (Polity)', meta: '98% match' },
  { label: 'News', color: 'blue', title: 'Hindu Summary', meta: '09:15 AM' },
];

export default function RecentActivity() {
  const { data: logs } = useActivityLogs();
  const items = logs?.slice(0, 4) || FALLBACK;

  return (
    <GlassCard className="col-span-4">
      <div className="text-sm font-medium text-white/70 mb-4">Recent Activity</div>
      <div className="grid grid-cols-4 gap-4">
        {items.map((item, i) => (
          <div key={i} className="glass p-4 flex flex-col gap-1.5">
            <StatusBadge label={item.label || item.stage || 'info'} color={item.color || 'gray'} />
            <div className="text-sm text-white font-medium truncate">{item.title || item.source_pdf || 'Activity'}</div>
            <div className="text-xs text-text-secondary">{item.meta || timeAgo(item.started_at) || ''}</div>
          </div>
        ))}
      </div>
    </GlassCard>
  );
}
