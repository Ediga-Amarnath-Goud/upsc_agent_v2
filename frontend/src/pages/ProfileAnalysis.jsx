import { useProfile } from '../hooks/useQueries';
import { useAnalyzeProfile } from '../hooks/useMutations';

export default function ProfileAnalysis() {
  const profile = useProfile();
  const analysisMut = useAnalyzeProfile();

  const handleRun = () => {
    analysisMut.mutate();
  };

  const p = profile.data;

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-2">Profile Analysis</h1>
      <p className="text-text-secondary text-sm mb-6">Review your performance and get a coach-generated report.</p>

      {/* Stats snapshot */}
      {p && (
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="glass p-4 text-center">
            <div className="text-2xl font-bold text-accent-blue">{p.total_attempted || 0}</div>
            <div className="text-xs text-text-secondary mt-1">Attempts</div>
          </div>
          <div className="glass p-4 text-center">
            <div className="text-2xl font-bold text-accent-green">{(p.accuracy * 100 || 0).toFixed(1)}%</div>
            <div className="text-xs text-text-secondary mt-1">Accuracy</div>
          </div>
          <div className="glass p-4 text-center">
            <div className="text-2xl font-bold text-yellow-400">{p.current_elo || 1200}</div>
            <div className="text-xs text-text-secondary mt-1">ELO</div>
          </div>
        </div>
      )}

      <button
        onClick={handleRun}
        disabled={analysisMut.isPending}
        className="w-full py-3 rounded-xl bg-accent-blue text-white font-medium text-sm hover:bg-accent-blue/80 disabled:opacity-40 transition mb-6"
      >
        {analysisMut.isPending ? 'Running analysis... (may take a moment)' : 'Run Analysis'}
      </button>

      {analysisMut.data && analysisMut.data.status === 'skipped' && (
        <div className="glass p-4 text-sm text-text-secondary">
          {analysisMut.data.message || 'Insufficient data. Need at least 50 attempts.'}
        </div>
      )}

      {analysisMut.data && (analysisMut.data.structured_data || analysisMut.data.coach_report) && (
        <div className="space-y-6">
          {analysisMut.data.structured_data && (
            <div className="glass p-5">
              <h2 className="text-sm font-semibold mb-3">Analysis Data</h2>
              <pre className="text-xs text-white/70 whitespace-pre-wrap max-h-96 overflow-y-auto">
                {JSON.stringify(analysisMut.data.structured_data, null, 2)}
              </pre>
            </div>
          )}
          {analysisMut.data.coach_report && (
            <div className="glass p-5">
              <h2 className="text-sm font-semibold mb-3">Coach Report</h2>
              <div className="text-sm text-white/80 leading-relaxed whitespace-pre-wrap">
                {analysisMut.data.coach_report}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
