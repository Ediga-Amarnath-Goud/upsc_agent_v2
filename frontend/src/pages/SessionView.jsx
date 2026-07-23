import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useSessionData } from '../hooks/useQueries';
import { useSubmitAnswer } from '../hooks/useMutations';
import StatusBadge from '../components/ui/StatusBadge';

function SessionInput({ onGo }) {
  const [val, setVal] = useState('');
  return (
    <div className="max-w-md mx-auto pt-16">
      <h1 className="text-2xl font-bold mb-2 text-center">Session View</h1>
      <p className="text-text-secondary text-sm mb-6 text-center">Enter a session ID to view and answer questions.</p>
      <div className="glass p-5 space-y-4">
        <input
          type="text"
          value={val}
          onChange={(e) => setVal(e.target.value)}
          placeholder="Session ID"
          className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white placeholder-text-secondary focus:outline-none focus:border-accent-blue/50"
        />
        <button
          onClick={() => val.trim() && onGo(val.trim())}
          className="w-full py-3 rounded-xl bg-accent-blue text-white font-medium text-sm hover:bg-accent-blue/80 transition"
        >
          Load Session
        </button>
      </div>
    </div>
  );
}

export default function SessionView() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data: session, isLoading, error } = useSessionData(id);
  const submitAnswer = useSubmitAnswer();

  const [currentIdx, setCurrentIdx] = useState(0);
  const [result, setResult] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [doneMessage, setDoneMessage] = useState('');

  if (!id) return <SessionInput onGo={(sid) => navigate(`/session/${sid}`)} />;

  if (isLoading) return <div className="text-center pt-16 text-text-secondary">Loading session...</div>;

  if (error) return (
    <div className="max-w-md mx-auto pt-16 text-center">
      <div className="text-accent-red text-lg mb-2">Session not found</div>
      <button onClick={() => navigate('/session')} className="text-accent-blue text-sm hover:underline">Try another ID</button>
    </div>
  );

  if (session.status === 'completed') {
    return (
      <div className="max-w-2xl mx-auto pt-8 text-center">
        <div className="text-4xl mb-4">🎯</div>
        <h1 className="text-2xl font-bold mb-2">Session Complete</h1>
        <p className="text-text-secondary text-sm mb-4">{session.topic_studied}</p>
        <div className="glass p-6 inline-block">
          <span className="text-5xl font-bold text-accent-blue">{session.score ?? 0}</span>
          <span className="text-text-secondary text-lg ml-2">/ {session.questions?.length || 0}</span>
        </div>
        <div className="mt-6">
          <button onClick={() => navigate('/')} className="text-accent-blue text-sm hover:underline">Back to Dashboard</button>
        </div>
      </div>
    );
  }

  const questions = session.questions || [];
  const responses = session.responses || {};
  const q = questions[currentIdx];
  const alreadyAnswered = String(currentIdx) in responses;

  const handleSubmit = (choice) => {
    if (submitting || alreadyAnswered) return;
    setSubmitting(true);
    submitAnswer.mutate(
      { session_id: id, question_index: currentIdx, response: choice },
      {
        onSuccess: (data) => {
          setResult(data);
          setSubmitting(false);
        },
        onError: () => setSubmitting(false),
      }
    );
  };

  const handleNext = () => {
    setResult(null);
    if (currentIdx + 1 < questions.length) {
      setCurrentIdx(currentIdx + 1);
    } else {
      // Check if all are answered
      const newResponses = { ...responses };
      if (result) newResponses[String(currentIdx)] = result.correct_answer;
      if (Object.keys(newResponses).length >= questions.length) {
        setDoneMessage('All questions answered!');
      } else {
        // Find next unanswered
        const nextUnanswered = questions.findIndex((_, i) => !(String(i) in { ...responses, [String(currentIdx)]: result?.correct_answer }));
        if (nextUnanswered >= 0) setCurrentIdx(nextUnanswered);
        else setDoneMessage('All questions answered!');
      }
    }
  };

  if (doneMessage) {
    return (
      <div className="max-w-2xl mx-auto pt-16 text-center">
        <div className="text-3xl mb-3">✅</div>
        <h1 className="text-xl font-bold mb-2">{doneMessage}</h1>
        <div className="text-text-secondary text-sm mb-4">Switch to the Dashboard to see your updated profile.</div>
        <button onClick={() => navigate('/')} className="text-accent-blue text-sm hover:underline">Dashboard</button>
      </div>
    );
  }

  if (!q) return <div className="text-center pt-16 text-text-secondary">No questions in this session.</div>;

  const answeredCount = Object.keys(responses).length + (result ? 1 : 0);

  return (
    <div className="max-w-3xl mx-auto pt-6">
      {/* Progress bar */}
      <div className="flex items-center gap-3 mb-6">
        <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
          <div className="h-full bg-accent-blue rounded-full transition-all" style={{ width: `${(answeredCount / questions.length) * 100}%` }} />
        </div>
        <span className="text-xs text-text-secondary shrink-0">{answeredCount}/{questions.length}</span>
      </div>

      {/* Question card */}
      <div className="glass p-6">
        <div className="flex items-start justify-between mb-4">
          <span className="text-xs text-text-secondary font-mono">Q{currentIdx + 1} of {questions.length}</span>
          <StatusBadge label={`tier ${q.difficulty_tier || '?'}`} color="gray" />
        </div>

        <h2 className="text-lg font-medium leading-relaxed mb-6">{q.question_text}</h2>

        <div className="space-y-2.5">
          {['A', 'B', 'C', 'D'].map((key) => {
            const isSelected = result && result.correct_answer === key;
            const isWrong = result && !result.correct && result.correct_answer !== key && result.correct_answer;
            const isUserWrong = result && !result.correct && result.correct_answer !== key;

            let border = 'border-white/10 hover:border-white/30';
            if (result?.correct_answer === key) border = 'border-accent-green';
            else if (isUserWrong && result?.correct_answer !== key) border = 'border-accent-red/50';

            return (
              <button
                key={key}
                onClick={() => handleSubmit(key)}
                disabled={submitting || alreadyAnswered || !!result}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl border bg-white/[0.02] text-left transition disabled:opacity-60 disabled:cursor-not-allowed ${border}`}
              >
                <span className="w-7 h-7 rounded-full bg-white/5 flex items-center justify-center text-sm font-medium shrink-0">
                  {key}
                </span>
                <span className="text-sm">{q.options?.[key] || ''}</span>
              </button>
            );
          })}
        </div>

        {/* Result */}
        {result && (
          <div className={`mt-5 p-4 rounded-xl border ${result.correct ? 'bg-accent-green/10 border-accent-green/20' : 'bg-accent-red/10 border-accent-red/20'}`}>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-lg">{result.correct ? '✅' : '❌'}</span>
              <span className="font-medium text-sm">{result.correct ? 'Correct!' : 'Incorrect'}</span>
              <span className="text-xs text-text-secondary ml-auto">ELO {result.elo_delta > 0 ? '+' : ''}{result.elo_delta}</span>
            </div>
            <div className="text-xs text-text-secondary space-y-1">
              <div><span className="text-white/60">Correct:</span> {result.correct_answer}</div>
              <div><span className="text-white/60">Trap:</span> {result.trap_explanation}</div>
              {result.most_likely_wrong_reason && (
                <div><span className="text-white/60">Why you might get it wrong:</span> {result.most_likely_wrong_reason}</div>
              )}
            </div>
          </div>
        )}

        {/* Next button */}
        {result && (
          <button onClick={handleNext} className="mt-4 w-full py-3 rounded-xl bg-accent-blue text-white font-medium text-sm hover:bg-accent-blue/80 transition">
            {currentIdx + 1 < questions.length ? 'Next Question →' : 'Finish'}
          </button>
        )}

        {/* Error */}
        {submitAnswer.isError && (
          <div className="mt-3 text-xs text-accent-red">
            {submitAnswer.error.response?.data?.detail || submitAnswer.error.message}
          </div>
        )}
      </div>
    </div>
  );
}
