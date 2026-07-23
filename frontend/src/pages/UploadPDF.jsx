import { useState, useRef, useCallback } from 'react';
import { useUploadPdf } from '../hooks/useMutations';
import { useActivityLog, useActivityLogs } from '../hooks/useQueries';
import { elapsed } from '../utils/format';
import StatusBadge from '../components/ui/StatusBadge';

export default function UploadPDF() {
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [logId, setLogId] = useState(null);
  const [uploadError, setUploadError] = useState(null);
  const fileRef = useRef();
  const { mutate, isPending } = useUploadPdf();
  const { data: progress } = useActivityLog(logId);
  const { data: allLogs } = useActivityLogs();

  const handleFile = useCallback((f) => {
    if (!f) return;
    const isPdf = f.type === 'application/pdf' || f.name?.toLowerCase().endsWith('.pdf');
    if (isPdf) { setFile(f); setUploadError(null); }
    else setUploadError('Only PDF files are accepted');
  }, []);

  const handleUpload = () => {
    if (!file) return;
    setUploadError(null);
    mutate(file, {
      onSuccess: (data) => setLogId(data.log_id),
      onError: (err) => setUploadError(err.response?.data?.detail || err.message),
    });
  };

  return (
    <div className="max-w-3xl mx-auto pt-8">
      <h1 className="text-2xl font-bold mb-2">Upload PDF</h1>
      <p className="text-text-secondary text-sm mb-6">Upload a UPSC Prelims PDF for trap analysis.</p>

      {/* Drop zone */}
      <div
        className={`glass p-10 text-center border-2 border-dashed transition ${
          dragOver ? 'border-accent-blue bg-accent-blue/5' : 'border-white/10'
        }`}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFile(e.dataTransfer.files[0]); }}
        onClick={() => fileRef.current?.click()}
      >
        <input
          ref={fileRef}
          type="file"
          accept=".pdf"
          className="hidden"
          onChange={(e) => handleFile(e.target.files[0])}
        />
        <div className="text-4xl mb-3">📄</div>
        <div className="text-white font-medium mb-1">
          {file ? file.name : 'Drop a PDF here or click to browse'}
        </div>
        {file && (
          <div className="text-xs text-text-secondary mb-3">
            {(file.size / 1024 / 1024).toFixed(1)} MB
          </div>
        )}
        {!file && <div className="text-xs text-text-secondary">Only .pdf files up to 50 MB</div>}
      </div>

      {/* Upload button */}
      {file && !logId && (
        <button
          onClick={handleUpload}
          disabled={isPending}
          className="mt-4 w-full py-3 rounded-xl bg-accent-blue text-white font-medium text-sm hover:bg-accent-blue/80 disabled:opacity-40 transition"
        >
          {isPending ? 'Uploading...' : 'Upload & Analyze'}
        </button>
      )}

      {/* Progress */}
      {logId && progress && (
        <div className="mt-6 glass p-5 space-y-3">
          <div className="flex items-center gap-2">
            <StatusBadge
              label={progress.status}
              color={progress.status === 'complete' ? 'green' : progress.status === 'failed' ? 'red' : 'blue'}
            />
            <span className="text-sm text-text-secondary capitalize">{progress.stage}</span>
          </div>
          {progress.progress && (
            <div className="w-full h-1.5 bg-white/10 rounded-full overflow-hidden">
              <div
                className="h-full bg-accent-blue rounded-full transition-all duration-500"
                style={{
                  width: progress.progress.includes('/')
                    ? `${(parseInt(progress.progress.split('/')[0]) / parseInt(progress.progress.split('/')[1])) * 100}%`
                    : '0%',
                }}
              />
            </div>
          )}
          <div className="text-xs text-text-secondary">
            {progress.progress || ''}
            {progress.completed_at ? ` · Done in ${elapsed(progress.started_at)}` : ''}
          </div>
          {progress.error && (
            <div className="text-xs text-accent-red bg-accent-red/10 p-2 rounded-lg">{progress.error}</div>
          )}
        </div>
      )}

      {/* Recent uploads */}
      {allLogs && allLogs.length > 0 && (
        <div className="mt-8">
          <h2 className="text-sm font-medium text-white/70 mb-3">Recent Uploads</h2>
          <div className="space-y-2">
            {allLogs.slice(0, 5).map((log) => (
              <div key={log.log_id} className="glass flex items-center justify-between px-4 py-3 text-sm">
                <span className="text-white truncate max-w-[300px]">{log.source_pdf}</span>
                <div className="flex items-center gap-3">
                  <StatusBadge
                    label={log.status}
                    color={log.status === 'complete' ? 'green' : log.status === 'failed' ? 'red' : 'blue'}
                  />
                  <span className="text-text-secondary text-xs">{elapsed(log.started_at)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
