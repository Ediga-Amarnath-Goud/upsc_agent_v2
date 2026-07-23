import { useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import { useCaList } from '../hooks/useQueries';
import { useCaFetch, useCaIngest } from '../hooks/useMutations';
import apiClient from '../api/client';

function _istDate(date) {
  const d = new Date(date);
  const istMs = d.getTime() + 330 * 60000;
  const istDate = new Date(istMs);
  const y = istDate.getUTCFullYear();
  const m = String(istDate.getUTCMonth() + 1).padStart(2, '0');
  const day = String(istDate.getUTCDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}
function todayStr() {
  return _istDate(new Date());
}
function yesterdayStr() {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return _istDate(d);
}

const PRIORITY_COLORS = { high: 'text-red-400', medium: 'text-yellow-400', low: 'text-text-secondary' };
const PRIORITY_ORDER = { high: 0, medium: 1, low: 2 };
const TABS = [
  { key: 'news', label: 'News', icon: '📰' },
  { key: 'official', label: 'Official Releases', icon: '📜' },
  { key: 'academy', label: 'Academy', icon: '🎓' },
  { key: 'all', label: 'All', icon: '📋' },
];
const OFFICIAL_SOURCES = ['pib'];
const ACADEMY_SOURCES = ['academy_pdf'];

export default function CurrentAffairs() {
  const [tab, setTab] = useState('news');
  const [dateFilter, setDateFilter] = useState('today');
  const [customDate, setCustomDate] = useState(todayStr());
  const [priority, setPriority] = useState('');
  const [search, setSearch] = useState('');
  const [fetchTriggeredAt, setFetchTriggeredAt] = useState(null);
  const [params, setParams] = useState({ page: 1, per_page: 20, date_fetched: todayStr() });
  const pollInterval = fetchTriggeredAt && (Date.now() - fetchTriggeredAt < 30000) ? 3000 : undefined;
  const { data: curatedData, isLoading, refetch } = useCaList(params, pollInterval);

  const fetchMut = useCaFetch();
  const ingestMut = useCaIngest();
  const [showIngest, setShowIngest] = useState(false);
  const [ingestUrl, setIngestUrl] = useState('');
  const [ingestText, setIngestText] = useState('');
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);

  const items = curatedData?.items || curatedData?.entries || [];
  const total = curatedData?.total || 0;

  const filteredItems = items.filter(e => {
    if (tab === 'official') return OFFICIAL_SOURCES.includes(e.source);
    if (tab === 'academy') return ACADEMY_SOURCES.includes(e.source);
    if (tab === 'news') return !OFFICIAL_SOURCES.includes(e.source) && !ACADEMY_SOURCES.includes(e.source);
    return true;
  });

  const sortedItems = [...filteredItems].sort((a, b) => {
    return (PRIORITY_ORDER[a.priority] ?? 1) - (PRIORITY_ORDER[b.priority] ?? 1);
  });

  const togglePriority = async (ev, item) => {
    ev.preventDefault();
    const cycle = { medium: 'high', high: 'low', low: 'medium' };
    const next = cycle[item.priority] || 'medium';
    await apiClient.patch(`/curated-ca/${item.id}`, { priority: next });
    refetch();
  };

  const handleFetch = () => {
    setFetchTriggeredAt(Date.now());
    fetchMut.mutate(undefined, { onSuccess: () => refetch() });
  };

  const handleIngest = () => {
    const body = {};
    if (ingestUrl.trim()) body.url = ingestUrl.trim();
    if (ingestText.trim()) body.text = ingestText.trim();
    ingestMut.mutate(body, {
      onSuccess: () => { setShowIngest(false); setIngestUrl(''); setIngestText(''); refetch(); },
    });
  };

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const form = new FormData();
      form.append('file', file);
      await apiClient.post('/current-affairs/upload-pdf', form);
      refetch();
    } catch (err) {
      alert(err.response?.data?.detail || err.message);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const updateParams = (overrides) => {
    setParams(p => ({ ...p, page: 1, ...overrides }));
  };

  const handleTabChange = (newTab) => {
    setTab(newTab);
    const base = { page: 1, per_page: 20 };
    if (dateFilter !== 'all') base.date_fetched = dateFilter === 'custom' ? customDate : dateFilter === 'today' ? todayStr() : yesterdayStr();
    setParams(base);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Current Affairs</h1>
          <p className="text-text-secondary text-sm mt-1">{total} entries</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowIngest(!showIngest)}
            className="px-4 py-2 rounded-xl bg-white/5 text-sm text-text-secondary hover:bg-white/10 transition">
            + Ingest
          </button>
          <button onClick={handleFetch} disabled={fetchMut.isPending}
            className="px-4 py-2 rounded-xl bg-accent-blue text-white text-sm font-medium hover:bg-accent-blue/80 disabled:opacity-40 transition">
            {fetchMut.isPending ? 'Fetching...' : 'Fetch Latest'}
          </button>
          <a href="/api/current-affairs/digest/pdf" target="_blank" rel="noopener noreferrer"
            className="px-4 py-2 rounded-xl bg-accent-green/20 text-accent-green text-sm font-medium hover:bg-accent-green/30 transition">
            Digest PDF
          </a>
          <input type="file" accept=".pdf" ref={fileRef} onChange={handleUpload} className="hidden" />
          <button onClick={() => fileRef.current?.click()} disabled={uploading}
            className="px-4 py-2 rounded-xl bg-accent-blue/20 text-accent-blue text-sm font-medium hover:bg-accent-blue/30 disabled:opacity-40 transition">
            {uploading ? 'Uploading...' : 'Upload PDF'}
          </button>
        </div>
      </div>

      {showIngest && (
        <div className="glass p-4 mb-6 space-y-3">
          <h3 className="text-sm font-medium">Manual Ingest</h3>
          <input type="text" placeholder="URL..." value={ingestUrl} onChange={e => setIngestUrl(e.target.value)}
            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2 text-sm" />
          <textarea placeholder="Or paste text..." value={ingestText} onChange={e => setIngestText(e.target.value)}
            rows={3} className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2 text-sm" />
          <button onClick={handleIngest}
            disabled={ingestMut.isPending || (!ingestUrl.trim() && !ingestText.trim())}
            className="px-4 py-2 rounded-xl bg-accent-blue text-white text-sm disabled:opacity-40 transition">
            {ingestMut.isPending ? 'Saving...' : 'Save'}
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b border-white/10 pb-2">
        {TABS.map(t => (
          <button key={t.key} onClick={() => handleTabChange(t.key)}
            className={`px-4 py-1.5 rounded-lg text-xs font-medium transition ${tab === t.key ? 'bg-accent-blue/20 text-accent-blue' : 'text-text-secondary hover:text-white hover:bg-white/5'}`}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2 mb-4">
        <button onClick={() => { setDateFilter('today'); updateParams({ date_fetched: todayStr() }); }}
          className={`px-3 py-1 rounded-lg text-xs font-medium transition ${dateFilter === 'today' ? 'bg-accent-blue text-white' : 'bg-white/5 text-text-secondary hover:bg-white/10'}`}>Today</button>
        <button onClick={() => { setDateFilter('yesterday'); updateParams({ date_fetched: yesterdayStr() }); }}
          className={`px-3 py-1 rounded-lg text-xs font-medium transition ${dateFilter === 'yesterday' ? 'bg-accent-blue text-white' : 'bg-white/5 text-text-secondary hover:bg-white/10'}`}>Yesterday</button>
        <button onClick={() => { setDateFilter('custom'); updateParams({ date_fetched: customDate }); }}
          className={`px-3 py-1 rounded-lg text-xs font-medium transition ${dateFilter === 'custom' ? 'bg-accent-blue text-white' : 'bg-white/5 text-text-secondary hover:bg-white/10'}`}>Custom</button>
        {dateFilter === 'custom' && (
          <input type="date" value={customDate} onChange={e => { setCustomDate(e.target.value); updateParams({ date_fetched: e.target.value }); }}
            className="bg-white/5 border border-white/10 rounded-lg px-2 py-1 text-xs text-white" />
        )}
        <button onClick={() => { setDateFilter('all'); updateParams({ date_fetched: undefined }); }}
          className={`px-3 py-1 rounded-lg text-xs font-medium transition ${dateFilter === 'all' ? 'bg-accent-blue text-white' : 'bg-white/5 text-text-secondary hover:bg-white/10'}`}>All</button>

        <span className="w-px h-5 bg-white/10 mx-1" />

        <button onClick={() => { setPriority(''); updateParams({ priority: undefined }); }}
          className={`px-3 py-1 rounded-lg text-xs font-medium transition ${priority === '' ? 'bg-accent-blue text-white' : 'bg-white/5 text-text-secondary hover:bg-white/10'}`}>All Priority</button>
        <button onClick={() => { setPriority('high'); updateParams({ priority: 'high' }); }}
          className={`px-3 py-1 rounded-lg text-xs font-medium transition ${priority === 'high' ? 'bg-red-400/20 text-red-400' : 'bg-white/5 text-text-secondary hover:bg-white/10'}`}>High</button>
        <button onClick={() => { setPriority('medium'); updateParams({ priority: 'medium' }); }}
          className={`px-3 py-1 rounded-lg text-xs font-medium transition ${priority === 'medium' ? 'bg-yellow-400/20 text-yellow-400' : 'bg-white/5 text-text-secondary hover:bg-white/10'}`}>Medium</button>
        <button onClick={() => { setPriority('low'); updateParams({ priority: 'low' }); }}
          className={`px-3 py-1 rounded-lg text-xs font-medium transition ${priority === 'low' ? 'bg-white/20 text-white' : 'bg-white/5 text-text-secondary hover:bg-white/10'}`}>Low</button>

        <span className="w-px h-5 bg-white/10 mx-1" />

        <input type="text" placeholder="Search..." value={search} onChange={e => setSearch(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') updateParams({ search: e.target.value || undefined }); }}
          className="bg-white/5 border border-white/10 rounded-lg px-3 py-1 text-xs text-white w-40 placeholder:text-text-secondary" />
        {search && <button onClick={() => { setSearch(''); updateParams({ search: undefined }); }}
          className="text-xs text-text-secondary hover:text-white">&times;</button>}
      </div>

      {isLoading ? (
        <p className="text-text-secondary text-sm">Loading...</p>
      ) : sortedItems.length === 0 ? (
        <div className="glass p-8 text-center">
          <p className="text-text-secondary text-sm">No entries yet. Click "Fetch Latest" to pull from RSS feeds.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {sortedItems.map(e => (
            <Link key={e.id} to={`/current-affairs/${e.id}`}
              className="glass p-4 block hover:bg-white/5 transition rounded-xl">
              <div className="flex items-start gap-3">
                <button onClick={ev => togglePriority(ev, e)}
                  className={`shrink-0 mt-0.5 text-xs font-bold ${PRIORITY_COLORS[e.priority] || 'text-text-secondary'} hover:scale-110 transition`}
                  title={`Priority: ${e.priority} — click to cycle`}>
                  {e.priority === 'high' ? '\u25B2' : e.priority === 'medium' ? '\u25CB' : '\u25BC'}
                </button>
                {e.image_url && (
                  <img src={`/api${e.image_url}`} alt=""
                    className="shrink-0 w-16 h-12 rounded-lg object-cover bg-white/5"
                    onError={ev => ev.target.style.display = 'none'} />
                )}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    {e.category && <span className="text-xs px-2 py-0.5 rounded-full bg-accent-blue/10 text-accent-blue">{e.category}</span>}
                    {e.gs_linkage && <span className="text-xs text-text-secondary">{e.gs_linkage}</span>}
                    <span className="text-xs text-text-secondary">{e.source}</span>
                    {OFFICIAL_SOURCES.includes(e.source) && (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-accent-green/15 text-accent-green">Official</span>
                    )}
                    {ACADEMY_SOURCES.includes(e.source) && (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-purple-500/15 text-purple-400">Academy PDF</span>
                    )}
                  </div>
                  <h3 className="text-sm font-medium truncate">{e.title}</h3>
                  {e.summary && <p className="text-xs text-text-secondary mt-1 line-clamp-2">{e.summary}</p>}
                </div>
              </div>
            </Link>
          ))}
          {total > params.per_page && (
            <div className="flex justify-center gap-2 pt-2">
              <button onClick={() => setParams(p => ({ ...p, page: Math.max(1, p.page - 1) }))}
                disabled={params.page <= 1}
                className="px-3 py-1 rounded-lg bg-white/5 text-xs disabled:opacity-30">&larr; Prev</button>
              <span className="text-xs text-text-secondary self-center">Page {params.page} / {Math.ceil(total / params.per_page)}</span>
              <button onClick={() => setParams(p => ({ ...p, page: p.page + 1 }))}
                disabled={params.page >= Math.ceil(total / params.per_page)}
                className="px-3 py-1 rounded-lg bg-white/5 text-xs disabled:opacity-30">Next &rarr;</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
