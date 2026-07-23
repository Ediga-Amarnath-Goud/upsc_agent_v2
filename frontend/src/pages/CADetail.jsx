import { useParams, Link } from 'react-router-dom';
import { useCaEntry } from '../hooks/useQueries';
import apiClient from '../api/client';
import { useState } from 'react';

const PRIORITY_CYCLE = { medium: 'high', high: 'low', low: 'medium' };
const PRIORITY_COLORS = { high: 'text-red-400 bg-red-400/10', medium: 'text-yellow-400 bg-yellow-400/10', low: 'text-text-secondary bg-white/5' };

function Tag({ label }) {
  return <span className="text-xs px-2 py-0.5 rounded-full bg-white/10 text-text-secondary">{label}</span>;
}

function Section({ title, children }) {
  return (
    <div className="glass p-4">
      <h3 className="text-sm font-semibold text-white/80 mb-2">{title}</h3>
      {children}
    </div>
  );
}

function ListSection({ title, items }) {
  if (!items || items.length === 0) return null;
  return (
    <Section title={title}>
      <ul className="list-disc list-inside space-y-1">
        {items.map((item, i) => (
          <li key={i} className="text-sm text-text-secondary leading-relaxed">{item}</li>
        ))}
      </ul>
    </Section>
  );
}

export default function CADetail() {
  const { id } = useParams();
  const { data, isLoading, refetch } = useCaEntry(id);
  const [imgError, setImgError] = useState(false);

  const imageSrc = data?.image_url?.startsWith('http') ? data.image_url : `/api${data?.image_url || ''}`;

  const togglePriority = async () => {
    if (!data) return;
    const next = PRIORITY_CYCLE[data.priority] || 'medium';
    await apiClient.patch(`/curated-ca/${data.id}`, { priority: next });
    refetch();
  };

  if (isLoading) return <p className="text-text-secondary text-sm">Loading...</p>;
  if (!data) return <p className="text-text-secondary text-sm">Entry not found.</p>;

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <Link to="/current-affairs" className="text-xs text-accent-blue hover:underline">&larr; Back</Link>

      {imageSrc && !imgError && (
        <div className="glass overflow-hidden rounded-xl">
          <img
            src={imageSrc}
            alt={data.title}
            className="w-full max-h-80 object-cover"
            onError={() => setImgError(true)}
          />
        </div>
      )}

      <div className="glass p-5 space-y-3">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {data.category && <span className="px-2 py-0.5 rounded-full bg-accent-blue/10 text-accent-blue">{data.category}</span>}
          {data.gs_linkage && <span className="text-text-secondary">{data.gs_linkage}</span>}
          {data.matched_via && <Tag label={data.matched_via.replace(/_/g, ' ')} />}
          {data.source === 'pib' && (
            <span className="px-2 py-0.5 rounded-full bg-accent-green/15 text-accent-green text-xs">Official Release</span>
          )}
          {data.matched_micro_topic && <Tag label={data.matched_micro_topic} />}
          {data.source && <span className="text-text-secondary">{data.source}</span>}
          {data.date_of_event && <span className="text-text-secondary">{data.date_of_event}</span>}
        </div>

        <div className="flex items-start justify-between gap-3">
          <h1 className="text-xl font-bold flex-1">{data.title}</h1>
          <button
            onClick={togglePriority}
            className={`shrink-0 text-xs px-2.5 py-1 rounded-full font-medium capitalize ${PRIORITY_COLORS[data.priority] || PRIORITY_COLORS.medium} hover:opacity-80 transition`}
            title="Toggle priority"
          >
            {data.priority}
          </button>
        </div>

        {data.summary && (
          <p className="text-sm text-text-secondary leading-relaxed whitespace-pre-line">{data.summary}</p>
        )}

        <div className="flex flex-wrap gap-1">
          {data.tags?.map((t, i) => <Tag key={i} label={t} />)}
        </div>

        {data.source_url && (
          <a href={data.source_url} target="_blank" rel="noopener noreferrer"
            className="inline-block text-xs text-accent-blue hover:underline">
            Read original source &rarr;
          </a>
        )}
      </div>

      {data.images?.length > 0 && (
        <Section title="Key Diagrams &amp; Visuals">
          <ul className="space-y-3">
            {data.images.map((desc, i) => (
              <li key={i} className="text-sm text-text-secondary leading-relaxed bg-white/5 rounded-lg p-3 border-l-2 border-accent-blue/40">
                {desc}
              </li>
            ))}
          </ul>
        </Section>
      )}

      <ListSection title="Supporting Arguments" items={data.supporting_arguments} />
      <ListSection title="Counter Arguments" items={data.counter_arguments} />
      <ListSection title="Way Forward" items={data.way_forward} />
      <ListSection title="Prelims High-Yield Facts" items={data.prelims_high_yield_facts} />

      {data.predicted_traps && (
        <Section title="Predicted Traps">
          {data.predicted_traps.description && (
            <p className="text-sm text-text-secondary mb-2">{data.predicted_traps.description}</p>
          )}
          {data.predicted_traps.likely_traps?.length > 0 && (
            <div className="mb-2">
              <p className="text-xs text-text-secondary mb-1">Likely traps:</p>
              <ul className="list-disc list-inside space-y-1">
                {data.predicted_traps.likely_traps.map((t, i) => (
                  <li key={i} className="text-sm text-text-secondary">{t}</li>
                ))}
              </ul>
            </div>
          )}
          {data.predicted_traps.avoidance_strategies?.length > 0 && (
            <div>
              <p className="text-xs text-text-secondary mb-1">Avoidance strategies:</p>
              <ul className="list-disc list-inside space-y-1">
                {data.predicted_traps.avoidance_strategies.map((s, i) => (
                  <li key={i} className="text-sm text-text-secondary">{s}</li>
                ))}
              </ul>
            </div>
          )}
        </Section>
      )}

      {data.is_academy_verified != null && (
        <div className="flex gap-4 text-xs text-text-secondary glass p-3">
          <span>{data.is_academy_verified ? '✓ Academy Verified' : '○ Not Verified'}</span>
          <span>{data.is_supplemental ? 'Supplemental' : 'Core'}</span>
        </div>
      )}
    </div>
  );
}
