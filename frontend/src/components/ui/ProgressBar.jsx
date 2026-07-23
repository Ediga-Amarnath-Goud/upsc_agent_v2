export default function ProgressBar({ value, color = 'accent-blue' }) {
  const colors = {
    'accent-blue': 'bg-accent-blue',
    'accent-green': 'bg-accent-green',
    'accent-orange': 'bg-accent-orange',
    'accent-yellow': 'bg-accent-yellow',
    'accent-red': 'bg-accent-red',
  };
  return (
    <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
      <div
        className={`h-full rounded-full transition-all duration-500 ${colors[color] || colors['accent-blue']}`}
        style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
      />
    </div>
  );
}
