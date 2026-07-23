import { useActivityLogs } from '../hooks/useQueries';
import StatusBadge from '../components/ui/StatusBadge';
import { elapsed } from '../utils/format';

export default function Logs() {
  const { data: logs, isLoading } = useActivityLogs();

  return (
    <div className="max-w-5xl mx-auto pt-4">
      <h1 className="text-2xl font-bold mb-2">Activity Log</h1>
      <p className="text-text-secondary text-sm mb-6">Pipeline processing history.</p>

      {isLoading && <div className="text-text-secondary text-sm">Loading...</div>}

      {logs && logs.length === 0 && (
        <div className="glass p-8 text-center text-text-secondary text-sm">
          No PDFs uploaded yet. Go upload one!
        </div>
      )}

      {logs && logs.length > 0 && (
        <div className="glass overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/5 text-text-secondary text-xs uppercase tracking-wider">
                <th className="text-left px-5 py-3 font-medium">File</th>
                <th className="text-left px-5 py-3 font-medium">Stage</th>
                <th className="text-left px-5 py-3 font-medium">Status</th>
                <th className="text-left px-5 py-3 font-medium">Progress</th>
                <th className="text-right px-5 py-3 font-medium">Elapsed</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.log_id} className="border-b border-white/5 hover:bg-white/[0.02] transition">
                  <td className="px-5 py-4 text-white font-medium">{log.source_pdf}</td>
                  <td className="px-5 py-4 text-text-secondary capitalize">{log.stage}</td>
                  <td className="px-5 py-4">
                    <StatusBadge
                      label={log.status}
                      color={log.status === 'complete' ? 'green' : log.status === 'failed' ? 'red' : log.status === 'in_progress' ? 'blue' : 'gray'}
                    />
                  </td>
                  <td className="px-5 py-4 text-text-secondary">{log.progress || '—'}</td>
                  <td className="px-5 py-4 text-right text-text-secondary">{elapsed(log.started_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
