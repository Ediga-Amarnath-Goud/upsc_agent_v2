import GlassCard from '../ui/GlassCard';

export default function WeeklyHeatmap() {
  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const levels = [0, 1, 2, 3];
  const data = Array.from({ length: 7 }, () =>
    Array.from({ length: 11 }, () => levels[Math.floor(Math.random() * 4)])
  );
  const colorMap = ['bg-white/5', 'bg-white/10', 'bg-accent-blue/40', 'bg-accent-blue/70'];

  return (
    <GlassCard className="flex flex-col gap-2">
      <div className="text-sm font-medium text-white/70">Weekly Heatmap</div>
      <div className="flex gap-1">
        {data.map((row, ri) => (
          <div key={ri} className="flex flex-col gap-1">
            {row.map((cell, ci) => (
              <div key={ci} className={`w-3 h-3 rounded-sm ${colorMap[cell]}`} />
            ))}
          </div>
        ))}
      </div>
      <div className="flex items-center gap-2 text-xs text-text-secondary mt-1">
        <span>Low</span>
        {levels.map(l => <div key={l} className={`w-3 h-3 rounded-sm ${colorMap[l]}`} />)}
        <span>High</span>
      </div>
    </GlassCard>
  );
}
