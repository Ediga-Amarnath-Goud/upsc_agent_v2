import GlassCard from '../ui/GlassCard';
import ProgressBar from '../ui/ProgressBar';

export default function SubjectProgress() {
  const subjects = [
    { label: 'GS1', value: 82, color: 'accent-green' },
    { label: 'GS2', value: 74, color: 'accent-yellow' },
    { label: 'GS3', value: 45, color: 'accent-orange' },
    { label: 'GS4', value: 61, color: 'accent-blue' },
  ];

  return (
    <GlassCard className="flex flex-col gap-4">
      <div className="text-sm font-medium text-white/70">Subject Progress</div>
      {subjects.map(s => (
        <div key={s.label}>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-white">{s.label}</span>
            <span className="text-text-secondary">{s.value}%</span>
          </div>
          <ProgressBar value={s.value} color={s.color} />
        </div>
      ))}
    </GlassCard>
  );
}
