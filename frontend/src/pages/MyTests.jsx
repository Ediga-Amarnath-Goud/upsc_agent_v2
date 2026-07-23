import { useState, useEffect } from 'react';
import apiClient from '../api/client';

export default function MyTests() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.get('/tests').then(r => { setData(r.data); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-text-secondary text-sm pt-8 text-center">Loading...</p>;

  const tests = data?.tests || [];
  const caDigests = data?.ca_digests || [];

  const noTests = !tests.length && !caDigests.length;

  return (
    <div className="max-w-5xl mx-auto pt-4">
      <h1 className="text-2xl font-bold mb-6">My Tests</h1>

      {noTests && (
        <div className="text-center pt-16">
          <p className="text-text-secondary text-sm">No tests generated yet. Head to <strong>Generate Test</strong> to create one.</p>
        </div>
      )}

      {/* Practice & Diagnostic Tests Table */}
      {tests.length > 0 && (
        <div className="mb-10">
          <h2 className="text-sm font-semibold mb-3 text-text-secondary uppercase tracking-wider">Practice & Diagnostic Tests</h2>
          <div className="glass overflow-hidden rounded-xl">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/5 text-text-secondary text-xs uppercase tracking-wider">
                  <th className="text-left px-4 py-3 font-medium">Type</th>
                  <th className="text-left px-4 py-3 font-medium">Topic</th>
                  <th className="text-left px-4 py-3 font-medium">Date</th>
                  <th className="text-center px-4 py-3 font-medium">Score</th>
                  <th className="text-center px-4 py-3 font-medium">Status</th>
                  <th className="text-right px-4 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {tests.map(t => (
                  <tr key={t.session_id} className="border-b border-white/5 hover:bg-white/5 transition">
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${t.type === 'diagnostic' ? 'bg-accent-green/10 text-accent-green' : 'bg-accent-blue/10 text-accent-blue'}`}>
                        {t.type === 'diagnostic' ? 'Diagnostic' : 'Practice'}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-medium truncate max-w-[200px]">{t.topic}</td>
                    <td className="px-4 py-3 text-text-secondary text-xs">{new Date(t.date).toLocaleDateString()}</td>
                    <td className="px-4 py-3 text-center">{t.score != null ? `${t.score}/${t.total}` : '-'}</td>
                    <td className="px-4 py-3 text-center">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${t.status === 'completed' ? 'bg-accent-green/10 text-accent-green' : 'bg-yellow-400/10 text-yellow-400'}`}>
                        {t.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex gap-2 justify-end">
                        {t.pdf_available && (
                          <a
                            href={`/api/${t.type === 'diagnostic' ? `diagnostic/question-paper?session_id=${t.session_id}` : `session/${t.session_id}/question-paper`}`}
                            target="_blank" rel="noopener noreferrer"
                            className="text-xs px-3 py-1.5 rounded-lg bg-accent-blue/10 text-accent-blue hover:bg-accent-blue/20 transition"
                          >
                            QP PDF
                          </a>
                        )}
                        {t.ak_available && (
                          <a
                            href={t.type === 'diagnostic' ? `/api/diagnostic/answer-key?session_id=${t.session_id}` : `/api/session/${t.session_id}/answer-key`}
                            target="_blank" rel="noopener noreferrer"
                            className="text-xs px-3 py-1.5 rounded-lg bg-accent-green/10 text-accent-green hover:bg-accent-green/20 transition"
                          >
                            AK PDF
                          </a>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Current Affairs Digests Grid */}
      {caDigests.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold mb-3 text-text-secondary uppercase tracking-wider">Current Affairs Digests</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {caDigests.map(d => (
              <div key={d.date} className="glass p-5 rounded-xl hover:bg-white/5 transition">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs px-2 py-0.5 rounded-full bg-accent-blue/10 text-accent-blue">Daily Digest</span>
                  <span className="text-xs text-text-secondary">{new Date(d.date).toLocaleDateString()}</span>
                </div>
                <p className="text-sm font-medium mb-1">{d.date}</p>
                <p className="text-xs text-text-secondary mb-4">{d.article_count} articles</p>
                <a
                  href={`/api${d.pdf_url}`}
                  target="_blank" rel="noopener noreferrer"
                  className="inline-block text-xs px-3 py-1.5 rounded-lg bg-accent-green/10 text-accent-green hover:bg-accent-green/20 transition"
                >
                  Download PDF
                </a>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}