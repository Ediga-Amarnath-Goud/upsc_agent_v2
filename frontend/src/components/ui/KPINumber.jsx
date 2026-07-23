export default function KPINumber({ value, unit, trend, trendUp }) {
  return (
    <div>
      <div className="kpi-number">{value}<span className="text-lg ml-1 text-text-secondary">{unit}</span></div>
      {trend !== undefined && (
        <span className={`text-sm font-medium ${trendUp ? 'text-accent-green' : 'text-accent-red'}`}>
          {trendUp ? '↑' : '↓'} {Math.abs(trend)}
        </span>
      )}
    </div>
  );
}
