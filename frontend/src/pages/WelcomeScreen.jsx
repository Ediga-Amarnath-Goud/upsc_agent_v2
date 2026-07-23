import { useNavigate } from 'react-router-dom';

export default function WelcomeScreen() {
  const navigate = useNavigate();

  return (
    <div className="h-screen w-screen flex flex-col items-center justify-center bg-[#0A0A0A] px-6">
      <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-accent-blue to-accent-green flex items-center justify-center mb-8 shadow-lg shadow-accent-blue/20">
        <span className="text-3xl font-bold text-white">U</span>
      </div>
      <h1 className="text-3xl font-bold mb-3">Welcome to UPSC Agent</h1>
      <p className="text-text-secondary text-center max-w-md text-sm leading-relaxed mb-10">
        Your AI-powered assistant for UPSC Prelims preparation.
        Analyse past papers, generate custom tests, track your traps,
        and get a personalised study plan.
      </p>
      <button
        onClick={() => navigate('/create-profile')}
        className="px-10 py-3.5 rounded-xl bg-accent-blue text-white font-medium hover:bg-accent-blue/80 transition text-base"
      >
        Get Started
      </button>
    </div>
  );
}
