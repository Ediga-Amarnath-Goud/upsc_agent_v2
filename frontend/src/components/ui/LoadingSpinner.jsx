export default function LoadingSpinner({ size = 24 }) {
  return (
    <div className="flex items-center justify-center p-8">
      <svg className="animate-spin" width={size} height={size} viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="10" stroke="rgba(255,255,255,0.1)" strokeWidth="3" />
        <path d="M12 2a10 10 0 0 1 10 10" stroke="#2D9CFF" strokeWidth="3" strokeLinecap="round" />
      </svg>
    </div>
  );
}
