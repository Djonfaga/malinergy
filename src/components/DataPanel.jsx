import React from 'react';
import useDataset from '../hooks/useDataset';

const CONFIDENCE_LABEL = {
  haute: 'Confiance haute',
  moyenne: 'Confiance moyenne',
  faible: 'Estimation',
};

export default function DataPanel() {
  const { data, error, loading, snapshot } = useDataset('metrics');

  return (
    <section className="data-panel">
      <div className="section-container">
        <div className="section-header">
          <div className="eyebrow">CHIFFRES CLÉS</div>
          <h2 className="section-title">L{'’'}état du secteur, chiffre par chiffre</h2>
          <p className="section-dek">
            {loading && 'Chargement des données…'}
            {error && 'Données indisponibles — lancer « python -m malinergy export ».'}
            {data && `Instantané ${snapshot}. Chaque valeur porte sa source ; les estimations sont signalées comme telles.`}
          </p>
        </div>

        {data && (
          <div className="metrics-grid">
            {data.metrics.map((m) => (
              <div key={m.id} className="metric-card card">
                <div className="metric-info">
                  <div className="metric-label">{m.label}</div>
                  <div className="metric-value">{m.value}</div>
                  <div className="metric-unit">{m.unit}</div>
                  <div className="metric-detail">{m.detail}</div>
                </div>
                <div className="metric-source">
                  <span className={`badge badge-${m.confidence}`}>
                    {CONFIDENCE_LABEL[m.confidence] || m.confidence}
                  </span>
                  <span className="metric-cite">{m.source}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      <style>{`
        .data-panel { padding: var(--s-12) 0; background-color: var(--bg-sunken); }
        .section-container { max-width: 1200px; margin: 0 auto; padding: 0 var(--s-5); }
        .section-header { margin-bottom: var(--s-8); max-width: 60ch; }
        .section-title { font-size: 32px; color: var(--mal-indigo-950); margin-bottom: var(--s-3); }
        .section-dek { color: var(--fg-muted); font-family: var(--font-mono); font-size: 13px; }
        .metrics-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--s-5); }
        .metric-card { display: flex; flex-direction: column; justify-content: space-between; gap: var(--s-4); }
        .metric-label { font-size: 14px; color: var(--fg-muted); }
        .metric-value { font-size: 30px; font-weight: 600; color: var(--mal-indigo-950); font-family: var(--font-mono); line-height: 1.1; }
        .metric-unit { font-size: 12px; color: var(--fg-muted); font-family: var(--font-mono); margin-top: var(--s-1); }
        .metric-detail { font-size: 13px; color: var(--fg-muted); margin-top: var(--s-3); line-height: 1.45; }
        .metric-source { border-top: 1px solid var(--border-soft); padding-top: var(--s-3); display: flex; flex-direction: column; gap: var(--s-2); }
        .metric-cite { font-size: 11px; color: var(--fg-muted); line-height: 1.4; }
        .badge { font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.06em; text-transform: uppercase; padding: 2px 6px; border-radius: var(--r-1); width: fit-content; }
        .badge-haute { background: #E3F1E4; color: #2E7D32; }
        .badge-moyenne { background: var(--mal-bone-200); color: var(--mal-indigo-700); }
        .badge-faible { background: #FBE9E7; color: #C62828; }
        @media (max-width: 960px) { .metrics-grid { grid-template-columns: repeat(2, 1fr); } }
        @media (max-width: 560px) { .metrics-grid { grid-template-columns: 1fr; } }
      `}</style>
    </section>
  );
}
