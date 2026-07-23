import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

export default function ConsentScreen() {
  const navigate = useNavigate();
  const [agreed, setAgreed] = useState(false);

  return (
    <div className="h-screen w-screen flex items-center justify-center bg-[#0A0A0A] px-6">
      <div className="w-full max-w-lg">
        <div className="text-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-accent-blue to-accent-green flex items-center justify-center mx-auto mb-4">
            <span className="text-xl font-bold text-white">U</span>
          </div>
          <h1 className="text-2xl font-bold">Diagnostic Test</h1>
          <p className="text-text-secondary text-sm mt-1">One-time assessment to calibrate your preparation</p>
        </div>

        <div className="glass p-8 space-y-5">
          <div className="space-y-3 text-sm text-text-secondary leading-relaxed">
            <p>
              This diagnostic test helps us understand your current level across all GS subjects.
              It contains <strong className="text-white">60 questions</strong> — a mix of past UPSC
              questions and fresh ones tailored to the syllabus.
            </p>
            <ul className="space-y-1.5">
              <li className="flex items-start gap-2">
                <span className="text-accent-blue mt-0.5">⏱</span>
                <span>You have <strong className="text-white">1 hour</strong> to complete it</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-accent-green mt-0.5">📚</span>
                <span>Covers Polity, History, Economy, Geography, Environment, Science & Culture</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-accent-yellow mt-0.5">🎯</span>
                <span>Your answers calibrate difficulty and identify your weak traps</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-accent-orange mt-0.5">🔒</span>
                <span>No score is shown — results are used internally to personalise your experience</span>
              </li>
            </ul>
            <p className="pt-2 border-t border-white/5">
              You can flag questions to review later. The test auto-submits when the timer runs out.
            </p>
          </div>

          <label className="flex items-start gap-3 cursor-pointer group">
            <input
              type="checkbox"
              checked={agreed}
              onChange={(e) => setAgreed(e.target.checked)}
              className="mt-0.5 accent-accent-blue w-4 h-4"
            />
            <span className="text-sm text-text-secondary group-hover:text-white/80 transition">
              I understand and agree to take the diagnostic test. It will be used to personalise my
              study plan and cannot be retaken.
            </span>
          </label>

          <button
            onClick={() => { localStorage.removeItem('diag_state'); navigate('/diagnostic'); }}
            disabled={!agreed}
            className="w-full py-3 rounded-xl bg-accent-blue text-white font-medium hover:bg-accent-blue/80 disabled:opacity-40 disabled:cursor-not-allowed transition"
          >
            Start Diagnostic
          </button>
        </div>
      </div>
    </div>
  );
}
