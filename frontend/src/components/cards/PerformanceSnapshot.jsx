import GlassCard from '../ui/GlassCard';
import { useProfile } from '../../hooks/useQueries';
import { LineChart, Line, ResponsiveContainer, YAxis } from 'recharts';

const sampleData = Array.from({ length: 20 }, (_, i) => ({ x: i + 1, y: 50 + Math.sin(i * 0.5) * 20 + Math.random() * 10 }));

export default function PerformanceSnapshot() {
  const { data: profile } = useProfile();
  const elo = profile?.current_elo || 1200;
  const acc = profile?.accuracy || 0;
  const delta = 18;

  return (
    <GlassCard className="flex flex-col gap-3">
      <div className="text-sm font-medium text-white/70">Performance Snapshot</div>
      <div className="flex items-baseline gap-2">
        <span className="kpi-number">{elo}</span>
        <span className="text-sm text-accent-green font-medium">+{delta}</span>
      </div>
      <div className="h-[80px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={sampleData}>
            <YAxis domain={[0, 100]} hide />
            <Line type="monotone" dataKey="y" stroke="#2D9CFF" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        <span className="text-text-secondary">Accuracy</span>
        <span className="text-right text-accent-green">{(acc * 100).toFixed(1)}%</span>
        <span className="text-text-secondary">GS1</span>
        <span className="text-right text-accent-green">+12.5%</span>
        <span className="text-text-secondary">GS2</span>
        <span className="text-right text-accent-green">+12.5%</span>
        <span className="text-text-secondary">GS3</span>
        <span className="text-right text-accent-yellow">+8.5%</span>
        <span className="text-text-secondary">GS4</span>
        <span className="text-right text-accent-blue">+7.5%</span>
        <span className="text-text-secondary border-t border-white/5 pt-1 mt-1">Overall</span>
        <span className="text-right text-accent-green border-t border-white/5 pt-1 mt-1">+2.5%</span>
      </div>
    </GlassCard>
  );
}
