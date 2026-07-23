import { useState } from 'react';
import { useMainsOcr } from '../hooks/useMutations';

export default function MainsOcr() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const mut = useMainsOcr();

  const handleFile = (e) => {
    const f = e.target.files[0];
    if (!f) return;
    setFile(f);
    setPreview(URL.createObjectURL(f));
  };

  const handleExtract = () => {
    if (!file) return;
    mut.mutate(file);
  };

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-2">Mains Answer OCR</h1>
      <p className="text-text-secondary text-sm mb-6">Upload a photo of a handwritten Mains answer sheet to extract text.</p>

      <div className="glass p-6 space-y-4">
        <label className="block">
          <span className="text-sm text-white/80 mb-1.5 block">Upload Image</span>
          <input
            type="file"
            accept="image/*"
            onChange={handleFile}
            className="w-full text-sm text-text-secondary file:mr-3 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-sm file:bg-accent-blue/10 file:text-accent-blue hover:file:bg-accent-blue/20"
          />
        </label>

        {preview && (
          <img src={preview} alt="Preview" className="max-h-80 rounded-xl object-contain bg-black/20" />
        )}

        <button
          onClick={handleExtract}
          disabled={!file || mut.isPending}
          className="w-full py-3 rounded-xl bg-accent-blue text-white font-medium text-sm hover:bg-accent-blue/80 disabled:opacity-40 transition"
        >
          {mut.isPending ? 'Extracting...' : 'Extract Text'}
        </button>
      </div>

      {mut.data && (
        <div className="glass p-5 mt-6 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold">Extracted Text</h2>
            {mut.data.confidence != null && (
              <span className="text-xs text-text-secondary">Confidence: {(mut.data.confidence * 100).toFixed(0)}%</span>
            )}
          </div>
          <pre className="text-sm text-white/80 whitespace-pre-wrap bg-black/20 p-4 rounded-xl max-h-96 overflow-y-auto">
            {mut.data.text || '(no text extracted)'}
          </pre>
        </div>
      )}

      {mut.isError && (
        <div className="mt-4 p-4 rounded-xl bg-accent-red/10 border border-accent-red/20 text-accent-red text-sm">
          {mut.error.response?.data?.detail || mut.error.message}
        </div>
      )}
    </div>
  );
}
