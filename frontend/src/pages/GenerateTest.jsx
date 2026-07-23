import { useState, useEffect, useRef } from 'react';
import { useGenerateTest, useSubmitOmr } from '../hooks/useMutations';
import { useSessionData } from '../hooks/useQueries';

function formatTime(sec) {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

export default function GenerateTest() {
  const [topic, setTopic] = useState('');
  const [count, setCount] = useState(10);
  const [sessionId, setSessionId] = useState(null);
  const [pdfUrl, setPdfUrl] = useState(null);
  const [timeLimit, setTimeLimit] = useState(1800);
  const [remaining, setRemaining] = useState(null);
  const [showOmr, setShowOmr] = useState(false);
  const [omrFile, setOmrFile] = useState(null);
  const timerRef = useRef(null);
  const startedRef = useRef(null);

  const generateMut = useGenerateTest();
  const submitOmrMut = useSubmitOmr();
  const sessionData = useSessionData(sessionId);

  // Start timer when PDF is shown
  useEffect(() => {
    if (!pdfUrl || startedRef.current) return;
    startedRef.current = Date.now();
    setRemaining(timeLimit);

    timerRef.current = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startedRef.current) / 1000);
      const r = Math.max(0, timeLimit - elapsed);
      setRemaining(r);
      if (r <= 0) {
        clearInterval(timerRef.current);
        setShowOmr(true);
        setPdfUrl(null);
      }
    }, 1000);

    return () => clearInterval(timerRef.current);
  }, [pdfUrl, timeLimit]);

  const handleGenerate = (e) => {
    e.preventDefault();
    if (!topic.trim()) return;
    generateMut.mutate(
      { topic_studied: topic.trim(), question_count: count, quality_check: false },
      {
        onSuccess: (data) => {
          setSessionId(data.session_id);
          setPdfUrl(data.pdf_url);
          setTimeLimit(data.time_limit_seconds || 1800);
          setShowOmr(false);
          setRemaining(null);
          startedRef.current = null;
          localStorage.setItem('last_test_session', data.session_id);
        },
      }
    );
  };

  const handleOmrSubmit = () => {
    if (!omrFile || !sessionId) return;
    submitOmrMut.mutate({ sessionId, file: omrFile });
  };

  const isEvaluated = sessionData.data?.status === 'completed';
  const pdfProxyUrl = pdfUrl ? `/api${pdfUrl}` : null;
  const lastSession = localStorage.getItem('last_test_session');

  return (
    <div className="max-w-4xl mx-auto pt-4">
      <h1 className="text-2xl font-bold mb-2">Generate Prelims Test</h1>
      <p className="text-text-secondary text-sm mb-6">Create a test, view it in-browser with a 30-minute timer, then submit your OMR.</p>

      {/* Recovery banner */}
      {!sessionId && lastSession && (
        <div className="glass p-4 mb-6 flex items-center justify-between">
          <span className="text-sm text-text-secondary">Last session: <span className="font-mono text-xs">{lastSession}</span></span>
          <a
            href={`/api/session/${lastSession}/question-paper`}
            target="_blank" rel="noopener noreferrer"
            className="text-xs px-3 py-1.5 rounded-lg bg-accent-blue/10 text-accent-blue hover:bg-accent-blue/20 transition"
          >
            Download PDF
          </a>
        </div>
      )}

      {/* Generation form */}
      {!pdfUrl && !sessionId && (
        <form onSubmit={handleGenerate} className="glass p-6 space-y-5 max-w-2xl">
          <div>
            <label className="block text-sm font-medium text-white/80 mb-1.5">Topic</label>
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. Medieval India, Polity, Economy..."
              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white placeholder-text-secondary focus:outline-none focus:border-accent-blue/50"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-white/80 mb-1.5">Questions: {count}</label>
            <input
              type="range"
              min={5}
              max={30}
              value={count}
              onChange={(e) => setCount(Number(e.target.value))}
              className="w-full accent-accent-blue"
            />
            <div className="flex justify-between text-xs text-text-secondary mt-1">
              <span>5</span>
              <span>30</span>
            </div>
          </div>
          <button
            type="submit"
            disabled={generateMut.isPending || !topic.trim()}
            className="w-full py-3 rounded-xl bg-accent-blue text-white font-medium text-sm hover:bg-accent-blue/80 disabled:opacity-40 disabled:cursor-not-allowed transition"
          >
            {generateMut.isPending ? 'Generating...' : 'Generate Test'}
          </button>
          {generateMut.isError && (
            <div className="p-4 rounded-xl bg-accent-red/10 border border-accent-red/20 text-accent-red text-sm">
              {generateMut.error.response?.data?.detail || generateMut.error.message}
            </div>
          )}
        </form>
      )}

      {/* PDF viewer + timer */}
      {pdfProxyUrl && remaining != null && (
        <div>
          <div className={`flex items-center justify-between mb-3 px-4 py-2 rounded-xl ${remaining < 120 ? 'bg-accent-red/10 border border-accent-red/20' : 'bg-white/5'}`}>
            <span className="text-sm text-text-secondary">Session: <span className="font-mono text-xs">{sessionId}</span></span>
            <span className={`text-xl font-mono font-bold ${remaining < 120 ? 'text-accent-red animate-pulse' : 'text-white'}`}>
              {formatTime(remaining)}
            </span>
          </div>
          <iframe
            src={pdfProxyUrl}
            className="w-full h-[70vh] rounded-xl border border-white/10"
            title="Question Paper"
          />
        </div>
      )}

      {/* OMR upload (shown after timer expires or manually triggered) */}
      {showOmr && sessionId && (
        <div className="glass p-6 max-w-xl mx-auto mt-4">
          <h2 className="text-sm font-semibold mb-1">Submit OMR</h2>
          <p className="text-xs text-text-secondary mb-4">Session: <span className="font-mono">{sessionId}</span></p>
          <input
            type="file"
            accept="image/*"
            onChange={e => setOmrFile(e.target.files[0])}
            className="w-full text-sm text-text-secondary file:mr-3 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-sm file:bg-accent-blue/10 file:text-accent-blue mb-4"
          />
          <button
            onClick={handleOmrSubmit}
            disabled={!omrFile || submitOmrMut.isPending}
            className="w-full py-3 rounded-xl bg-accent-blue text-white font-medium text-sm hover:bg-accent-blue/80 disabled:opacity-40 transition"
          >
            {submitOmrMut.isPending ? 'Submitting...' : 'Submit OMR'}
          </button>
          {submitOmrMut.data && (
            <div className="mt-4 p-3 rounded-xl bg-accent-green/10 text-accent-green text-sm">
              OMR submitted — {submitOmrMut.data.correct_count || 0} / {submitOmrMut.data.total_questions || 0} correct
            </div>
          )}
        </div>
      )}

      {/* Evaluation results */}
      {isEvaluated && (
        <div className="glass p-5 mt-6">
          <h2 className="text-sm font-semibold mb-3">Results</h2>
          <div className="grid grid-cols-3 gap-4 mb-4">
            <div className="text-center">
              <div className="text-xl font-bold text-accent-blue">{sessionData.data.total_questions}</div>
              <div className="text-xs text-text-secondary">Questions</div>
            </div>
            <div className="text-center">
              <div className="text-xl font-bold text-accent-green">{sessionData.data.score || sessionData.data.correct_count}</div>
              <div className="text-xs text-text-secondary">Correct</div>
            </div>
            <div className="text-center">
              <div className="text-xl font-bold text-yellow-400">{sessionData.data.elo_delta || 0}</div>
              <div className="text-xs text-text-secondary">ELO Δ</div>
            </div>
          </div>
          <div className="flex gap-3">
            <a
              href={`/api/session/${sessionId}/question-paper`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 py-2.5 rounded-xl bg-accent-green/20 text-accent-green text-sm font-medium text-center hover:bg-accent-green/30 transition"
            >
              📄 Question Paper
            </a>
            <button className="flex-1 py-2.5 rounded-xl bg-accent-blue/20 text-accent-blue text-sm font-medium text-center hover:bg-accent-blue/30 transition">
              📖 Answer Key (PDF)
            </button>
          </div>
        </div>
      )}

      {/* Reset */}
      {sessionId && !pdfUrl && !showOmr && !isEvaluated && (
        <button
          onClick={() => { setSessionId(null); setPdfUrl(null); setOmrFile(null); setShowOmr(false); setRemaining(null); startedRef.current = null; }}
          className="mt-4 text-xs text-text-secondary hover:text-white underline"
        >
          ← Generate another test
        </button>
      )}
    </div>
  );
}
