export default function GlassCard({ children, className = '', gradient = false }) {
  return (
    <div className={`glass p-5 ${gradient ? 'gradient-blue' : ''} ${className}`}>
      {children}
    </div>
  );
}
