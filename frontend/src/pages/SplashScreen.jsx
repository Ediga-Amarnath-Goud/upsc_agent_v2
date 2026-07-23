import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

export default function SplashScreen() {
  const navigate = useNavigate();

  useEffect(() => {
    const t = setTimeout(() => navigate('/welcome', { replace: true }), 2500);
    return () => clearTimeout(t);
  }, [navigate]);

  return (
    <div className="h-screen w-screen flex flex-col items-center justify-center bg-[#0A0A0A]">
      <div className="animate-pulse-slow">
        <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-accent-blue to-accent-green flex items-center justify-center mx-auto mb-6 shadow-lg shadow-accent-blue/20">
          <span className="text-3xl font-bold text-white">U</span>
        </div>
      </div>
      <h1 className="text-xl font-semibold text-white/80 tracking-wide">UPSC Agent</h1>
      <p className="text-text-secondary text-sm mt-2">Preparing you, one question at a time</p>
    </div>
  );
}
