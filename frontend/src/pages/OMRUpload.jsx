import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSubmitOmr } from '../hooks/useMutations';
import StatusBadge from '../components/ui/StatusBadge';

export default function OMRUpload() {
  const [sessionId, setSessionId] = useState('');
  const [file, setFile] = useState(null);
  const fileRef = useRef();
  const navigate = useNavigate();
  const { mutate, data, isPending, error } = useSubmitOmr();

  const handleSubmit = () => {
    if (!sessionId.trim() || !file) return;
    mutate({ sessionId: sessionId.trim(), file });
  };

  const reset = () => {
    setFile(null);
    setSessionId('');
  };

  // If no results, show input form
  if (!data) {
    return (
      <div className="max-w-2xl mx-auto pt-8">
        <h1 className="text-2xl font-bold mb-2">Submit OMR Answer Sheet</h1>
        <p className="text-text-secondary text-sm mb-6">Upload a scanned/photo of your OMR sheet. Gemini Vision reads the bubbles and scores your test.</p>

        <div className="glass p-6 space-y-5">
          <div>
            <label className="block text-sm font-medium text-white/80 mb-1.5">Session ID</label>
            <input
              type="text"
              value={sessionId}
              onChange={(e) => setSessionId(e.target.value)}
              placeholder="e.g. a1b2c3d4-..."
              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white placeholder-text-secondary focus:outline-none focus:border-accent-blue/50"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-white/80 mb-1.5">OMR Image</label>
            <div
              className="glass p-8 text-center border-2 border-dashed border-white/10 hover:border-accent-blue/50 transition cursor-pointer"
              onClick={() => fileRef.current?.click()}
            >
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => setFile(e.target.files[0])}
              />
              <div className="text-3xl mb-2">📷</div>
              <div className="text-sm text-white font-medium">
                {file ? file.name : 'Click to upload OMR image'}
              </div>
              {file && (
                <div className="text-xs text-text-secondary mt-1">
                  {(file.size / 1024 / 1024).toFixed(1)} MB
                </div>
              )}
            </div>
          </div>

          <button
            onClick={handleSubmit}
            disabled={isPending || !sessionId.trim() || !file}
            className="w-full py-3 rounded-xl bg-accent-blue text-white font-medium text-sm hover:bg-accent-blue/80 disabled:opacity-40 transition"
          >
            {isPending ? 'Reading bubbles...' : 'Submit OMR'}
          </button>

          {error && (
            <div className="text-xs text-accent-red bg-accent-red/10 p-3 rounded-lg">
              {error.response?.data?.detail || error.message}
            </div>
          )}
        </div>
      </div>
    );
  }

  // Results
  const correctCount = data.correct_count || 0;
  const total = data.total_questions || 0;
  const results = data.results || [];

  return (
    <div className="max-w-4xl mx-auto pt-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">OMR Results</h1>
          <p className="text-text-secondary text-sm">Session scored · ELO {data.elo_delta > 0 ? '+' : ''}{data.elo_delta}</p>
        </div>
        <div className="text-right">
          <span className="text-4xl font-bold text-accent-blue">{correctCount}</span>
          <span className="text-text-secondary text-lg ml-1">/ {total}</span>
        </div>
      </div>

      <div className="glass overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/5 text-text-secondary text-xs uppercase tracking-wider">
              <th className="text-left px-4 py-3 font-medium">#</th>
              <th className="text-left px-4 py-3 font-medium">Your Answer</th>
              <th className="text-left px-4 py-3 font-medium">Correct</th>
              <th className="text-left px-4 py-3 font-medium">Result</th>
              <th className="text-left px-4 py-3 font-medium">Trap</th>
            </tr>
          </thead>
          <tbody>
            {results.map((r, i) => (
              <tr key={i} className="border-b border-white/5 hover:bg-white/[0.02]">
                <td className="px-4 py-3 text-text-secondary font-mono">{r.question_index + 1}</td>
                <td className="px-4 py-3">
                  <span className="font-mono text-white">{r.response}</span>
                </td>
                <td className="px-4 py-3">
                  <span className="font-mono text-accent-green">{r.correct_answer}</span>
                </td>
                <td className="px-4 py-3">
                  {r.correct
                    ? <span className="text-accent-green">✓</span>
                    : <span className="text-accent-red">✗</span>
                  }
                </td>
                <td className="px-4 py-3 text-xs text-text-secondary max-w-[200px] truncate" title={r.trap_explanation}>
                  {r.trap_explanation}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {results.length > 10 && (
        <div className="mt-2 text-xs text-text-secondary text-center">
          Showing all {results.length} responses
        </div>
      )}

      <div className="flex gap-3 mt-6">
        <button onClick={reset} className="flex-1 py-3 rounded-xl bg-white/5 text-white font-medium text-sm hover:bg-white/10 transition">
          Score Another OMR
        </button>
        <button onClick={() => navigate('/')} className="flex-1 py-3 rounded-xl bg-accent-blue/20 text-accent-blue font-medium text-sm hover:bg-accent-blue/30 transition">
          Dashboard
        </button>
      </div>
    </div>
  );
}
