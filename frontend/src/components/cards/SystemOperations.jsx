import GlassCard from '../ui/GlassCard';
import { useHealth } from '../../hooks/useQueries';

export default function SystemOperations() {
  const { data: health } = useHealth();

  return (
    <GlassCard className="flex flex-col gap-2.5">
      <div className="text-sm font-medium text-white/70">System Operations</div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
        <span className="text-text-secondary">Backend Status</span>
        <span className="text-right text-accent-green">{health?.status || 'checking...'}</span>
        <span className="text-text-secondary">Workers</span>
        <span className="text-right text-accent-green">8/8</span>
        <span className="text-text-secondary">Latency</span>
        <span className="text-right text-accent-green">12ms</span>
        <span className="text-text-secondary">Model</span>
        <span className="text-right text-accent-blue text-[10px] truncate">{health?.model || '...'}</span>
        <span className="text-text-secondary">Queue</span>
        <span className="text-right text-accent-yellow">2 files</span>
        <span className="text-text-secondary">Confidence</span>
        <span className="text-right text-accent-green">95.8%</span>
        <span className="text-text-secondary">OCR Provider</span>
        <span className="text-right text-accent-blue">Google Vision API</span>
        <span className="text-text-secondary">Heartbeat</span>
        <span className="text-right text-accent-green">Active (5s ago)</span>
        <span className="text-text-secondary">Pending Tests</span>
        <span className="text-right text-accent-orange">3 Tests Pending</span>
        <span className="text-text-secondary">Sync Status</span>
        <span className="text-right text-white/70">Google Drive</span>
      </div>
    </GlassCard>
  );
}
