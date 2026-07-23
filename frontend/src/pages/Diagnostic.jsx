import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useStartDiagnostic, useSubmitDiagnostic } from '../hooks/useMutations';

const LS_KEY = 'diag_state';
const TIME_LIMIT = 3600;

function loadState() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

function saveState(s) {
  localStorage.setItem(LS_KEY, JSON.stringify(s));
}

function clearState() {
  localStorage.removeItem(LS_KEY);
}

function formatTime(sec) {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

export default function Diagnostic() {
  const navigate = useNavigate();
  const [state, setState] = useState(() => loadState());
  const [currentIdx, setCurrentIdx] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef(null);
  const startMutation = useStartDiagnostic();
  const submitMutation = useSubmitDiagnostic();

  const isRunning = state && !state.submitted && state.startedAt;
  const questions = state?.questions || [];
  const total = questions.length;
  const responses = state?.responses || {};
  const flagged = state?.flagged || [];

  // Timer
  useEffect(() => {
    if (!isRunning) return;
    timerRef.current = setInterval(() => {
      const now = Date.now();
      const started = new Date(state.startedAt).getTime();
      const e = Math.floor((now - started) / 1000);
      setElapsed(e);
      if (e >= TIME_LIMIT) {
        clearInterval(timerRef.current);
        handleAutoSubmit();
      }
    }, 1000);
    return () => clearInterval(timerRef.current);
  }, [isRunning]);

  const updateState = useCallback((patch) => {
    setState(prev => {
      const next = { ...prev, ...patch };
      saveState(next);
      return next;
    });
  }, []);

  const handleStart = async () => {
    try {
      const data = await startMutation.mutateAsync();
      // data: { session_id, total, time_limit_seconds, question_paper_url, questions }
      const newState = {
        sessionId: data.session_id,
        startedAt: new Date().toISOString(),
        questions: data.questions || [],
        responses: {},
        flagged: [],
        submitted: false,
      };
      updateState(newState);
      setCurrentIdx(0);
    } catch (e) {
      alert(e.response?.data?.detail || e.message);
    }
  };

  const handleSelect = (option) => {
    const newResponses = { ...responses, [currentIdx]: option };
    updateState({ responses: newResponses });
  };

  const toggleFlag = () => {
    const f = flagged.includes(currentIdx)
      ? flagged.filter(i => i !== currentIdx)
      : [...flagged, currentIdx];
    updateState({ flagged: f });
  };

  const goTo = (i) => { if (i >= 0 && i < total) setCurrentIdx(i); };

  const handleAutoSubmit = () => {
    if (submitMutation.isPending || state?.submitted) return;
    doSubmit();
  };

  const doSubmit = async () => {
    try {
      const cleanResponses = {};
      for (const [k, v] of Object.entries(responses)) {
        if (v) cleanResponses[k] = v;
      }
      const profileDraft = JSON.parse(localStorage.getItem('profile_draft') || '{}');
      const payload = {
        session_id: state.sessionId,
        responses: cleanResponses,
      };
      if (profileDraft.name) {
        payload.name = profileDraft.name;
        payload.age = profileDraft.age;
        payload.gender = profileDraft.gender;
      }
      await submitMutation.mutateAsync(payload);
      localStorage.removeItem('profile_draft');
      updateState({ submitted: true });
      clearState();
    } catch (e) {
      alert(e.response?.data?.detail || e.message);
    }
  };

  const remaining = TIME_LIMIT - elapsed;
  const timerUrgent = remaining < 300;

  // Start screen
  if (!state || (!state.submitted && !state.startedAt)) {
    return (
      <div className="max-w-xl mx-auto pt-16 text-center">
        <h1 className="text-3xl font-bold mb-3">Diagnostic Test</h1>
        <p className="text-text-secondary text-sm mb-6">
          60 questions covering Polity, History, Economy, Geography, Environment, Science, and Culture.
          You have <strong>1 hour</strong>. No score is shown after submission.
        </p>
        <div className="glass p-6 text-left text-sm text-text-secondary space-y-3 mb-8">
          <p>✔ 25 previous year questions + 35 fresh questions</p>
          <p>✔ One question at a time — navigate using the palette</p>
          <p>✔ Flag questions to review later</p>
          <p>✔ Auto-submits when the timer expires</p>
          <p>✔ Answer key PDF available after completion</p>
        </div>
        <button
          onClick={handleStart}
          disabled={startMutation.isPending}
          className="px-8 py-3 rounded-xl bg-accent-blue text-white font-medium hover:bg-accent-blue/80 disabled:opacity-40 transition"
        >
          {startMutation.isPending ? 'Generating...' : 'Start Diagnostic'}
        </button>
        {startMutation.isError && (
          <p className="mt-4 text-accent-red text-sm">{startMutation.error.response?.data?.detail || startMutation.error.message}</p>
        )}
      </div>
    );
  }

  // Submitted screen
  if (state.submitted) {
    return (
      <div className="max-w-xl mx-auto pt-16 text-center">
        <div className="text-5xl mb-4">✅</div>
        <h1 className="text-2xl font-bold mb-2">Diagnostic Completed</h1>
        <p className="text-text-secondary text-sm mb-6">Your diagnostic has been submitted successfully.</p>
        <div className="flex items-center justify-center gap-3">
          <a
            href={`/api/diagnostic/answer-key?session_id=${state.sessionId}`}
            target="_blank"
            rel="noopener noreferrer"
            className="px-6 py-3 rounded-xl bg-accent-green/20 text-accent-green text-sm font-medium hover:bg-accent-green/30 transition"
          >
            📄 Download Answer Key PDF
          </a>
          <button
            onClick={() => navigate('/')}
            className="px-6 py-3 rounded-xl bg-accent-blue text-white text-sm font-medium hover:bg-accent-blue/80 transition"
          >
            Go to Dashboard
          </button>
        </div>
      </div>
    );
  }

  // Test in progress
  const q = questions[currentIdx];
  const opts = q?.options || {};
  const answeredCount = Object.keys(responses).length;
  const flaggedCount = flagged.length;

  return (
    <div className="flex flex-col h-full">
      {/* Timer bar */}
      <div className={`flex items-center justify-between px-6 py-3 rounded-xl mb-4 ${timerUrgent ? 'bg-accent-red/10 border border-accent-red/20' : 'bg-white/5'}`}>
        <div className="flex gap-4 text-sm">
          <span>Answered: <strong className="text-accent-blue">{answeredCount}</strong>/{total}</span>
          <span>Flagged: <strong className="text-yellow-400">{flaggedCount}</strong></span>
        </div>
        <div className={`text-xl font-mono font-bold ${timerUrgent ? 'text-accent-red animate-pulse' : 'text-white'}`}>
          {formatTime(Math.max(0, remaining))}
        </div>
      </div>

      <div className="flex gap-6 flex-1 min-h-0">
        {/* Question palette */}
        <div className="w-48 shrink-0 overflow-y-auto">
          <div className="grid grid-cols-5 gap-1.5">
            {questions.map((_, i) => {
              const isCurrent = i === currentIdx;
              const isAnswered = responses[i] != null;
              const isFlagged = flagged.includes(i);
              let cls = 'w-8 h-8 rounded-lg text-xs font-medium flex items-center justify-center transition cursor-pointer ';
              if (isCurrent) cls += 'ring-2 ring-accent-blue bg-accent-blue/20 text-accent-blue';
              else if (isFlagged) cls += 'bg-yellow-400/20 text-yellow-400';
              else if (isAnswered) cls += 'bg-accent-blue/10 text-accent-blue';
              else cls += 'bg-white/5 text-text-secondary hover:bg-white/10';
              return (
                <button key={i} className={cls} onClick={() => goTo(i)}>
                  {i + 1}
                </button>
              );
            })}
          </div>
        </div>

        {/* Question card */}
        <div className="flex-1 flex flex-col min-h-0">
          <div className="glass p-6 flex-1 overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <span className="text-xs text-text-secondary font-mono">Q{currentIdx + 1} / {total}</span>
              <button
                onClick={toggleFlag}
                className={`text-xs px-3 py-1 rounded-lg border transition ${flagged.includes(currentIdx) ? 'border-yellow-400/40 text-yellow-400 bg-yellow-400/10' : 'border-white/10 text-text-secondary hover:border-white/20'}`}
              >
                {flagged.includes(currentIdx) ? '★ Flagged' : '☆ Flag'}
              </button>
            </div>
            <p className="text-base leading-relaxed mb-6">{q?.question_text}</p>
            <div className="space-y-2">
              {['A', 'B', 'C', 'D'].map(key => (
                <label
                  key={key}
                  className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition ${responses[currentIdx] === key ? 'border-accent-blue bg-accent-blue/5' : 'border-white/10 hover:border-white/20'}`}
                >
                  <input
                    type="radio"
                    name="q"
                    value={key}
                    checked={responses[currentIdx] === key}
                    onChange={() => handleSelect(key)}
                    className="accent-accent-blue"
                  />
                  <span className="font-medium text-sm w-6">{key}.</span>
                  <span className="text-sm text-white/80">{opts[key] || ''}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Navigation buttons */}
          <div className="flex items-center justify-between mt-4">
            <div className="flex gap-2">
              <button
                onClick={() => goTo(currentIdx - 1)}
                disabled={currentIdx === 0}
                className="px-4 py-2 rounded-xl bg-white/5 text-sm text-text-secondary hover:bg-white/10 disabled:opacity-30 transition"
              >
                ← Prev
              </button>
              <button
                onClick={() => goTo(currentIdx + 1)}
                disabled={currentIdx >= total - 1}
                className="px-4 py-2 rounded-xl bg-white/5 text-sm text-text-secondary hover:bg-white/10 disabled:opacity-30 transition"
              >
                Next →
              </button>
            </div>
            <div className="flex gap-2">
              <span className="text-xs text-text-secondary self-center mr-2">{total - answeredCount} unanswered</span>
              <button
                onClick={doSubmit}
                disabled={submitMutation.isPending}
                className="px-6 py-2 rounded-xl bg-accent-green/20 text-accent-green text-sm font-medium hover:bg-accent-green/30 disabled:opacity-40 transition"
              >
                {submitMutation.isPending ? 'Submitting...' : 'Submit Test'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
