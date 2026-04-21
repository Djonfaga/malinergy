import React from 'react';

export default function DataPanel() {
  const metrics = [
    { label: 'Capacité installée', value: '850 MW', change: '+5%', icon: 'ph-lightning' },
    { label: 'Accès national', value: '54%', change: '+2%', icon: 'ph-house-line' },
    { label: 'Part EnR', value: '38%', change: '+12%', icon: 'ph-sun' },
    { label: 'Pertés réseau', value: '18%', change: '-1%', icon: 'ph-chart-line-down' },
  ];

  return (
    <section className="data-panel">
      <div className="section-container">
        <div className="section-header">
          <div className="eyebrow">CHIFFRES CLÉS</div>
          <h2 className="section-title">L'état du secteur en temps réel</h2>
          <p className="section-dek">Sources : EDM-SA, CREE, Ministère de l'Énergie. Dernière mise à jour : 14 mars 2026.</p>
        </div>
        <div className="metrics-grid">
          {metrics.map((m, i) => (
            <div key={i} className="metric-card card">
              <div className="metric-icon">
                <i className={`ph ${m.icon}`}></i>
              </div>
              <div className="metric-info">
                <div className="metric-label">{m.label}</div>
                <div className="metric-value">{m.value}</div>
                <div className={`metric-change ${m.change.startsWith('+') ? 'pos' : 'neg'}`}>
                  {m.change} par rapport à 2023
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
      <style>{`
        .data-panel {
          padding: var(--s-12) 0;
          background-color: var(--bg-sunken);
        }
        .section-container {
          max-width: 1200px;
          margin: 0 auto;
          padding: 0 var(--s-5);
        }
        .section-header {
          margin-bottom: var(--s-8);
          max-width: 60ch;
        }
        .section-title {
          font-size: 32px;
          color: var(--mal-indigo-950);
          margin-bottom: var(--s-3);
        }
        .section-dek {
          color: var(--fg-muted);
          font-family: var(--font-mono);
          font-size: 13px;
        }
        .metrics-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: var(--s-5);
        }
        .metric-card {
          display: flex;
          flex-direction: column;
          gap: var(--s-4);
        }
        .metric-icon {
          width: 40px;
          height: 40px;
          border-radius: var(--r-2);
          background: var(--mal-bone-200);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 20px;
          color: var(--mal-indigo-700);
        }
        .metric-label {
          font-size: 14px;
          color: var(--fg-muted);
        }
        .metric-value {
          font-size: 28px;
          font-weight: 600;
          color: var(--mal-indigo-950);
          font-family: var(--font-mono);
        }
        .metric-change {
          font-size: 12px;
          margin-top: var(--s-1);
        }
        .metric-change.pos { color: #2E7D32; }
        .metric-change.neg { color: #C62828; }
      `}</style>
    </section>
  );
}
