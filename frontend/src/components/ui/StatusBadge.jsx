export default function StatusBadge({ label, color = 'green' }) {
  const colors = {
    green: 'bg-accent-green/20 text-accent-green border-accent-green/30',
    blue: 'bg-accent-blue/20 text-accent-blue border-accent-blue/30',
    orange: 'bg-accent-orange/20 text-accent-orange border-accent-orange/30',
    red: 'bg-accent-red/20 text-accent-red border-accent-red/30',
    yellow: 'bg-accent-yellow/20 text-accent-yellow border-accent-yellow/30',
    gray: 'bg-white/5 text-text-secondary border-white/10',
  };
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border ${colors[color] || colors.gray}`}>
      <span className={`w-1.5 h-1.5 rounded-full bg-current`} />
      {label}
    </span>
  );
}
