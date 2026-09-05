import React, { useState } from 'react';
import useDataset from '../hooks/useDataset';

const CATEGORIES = [
  {
    id: 'sans regret',
    label: 'Sans regret',
    blurb: 'Rentables, réalisables, sans prérequis de réforme non acquis.',
  },
  {
    id: 'conditionnel',
    label: 'Conditionnel',
    blurb: 'Le gain est réel mais suppose une condition structurelle aujourd’hui absente.',
  },
  {
    id: 'à préparer',
    label: 'À préparer',
    blurb: 'Le délai ou le retour dépasse le cycle de la crise courante.',
    match: 'a preparer',
  },
];

const RISK_LABEL = { faible: 'faible', moyen: 'moyen', eleve: 'élevé' };

const milliards = (value) =>
  `${(value / 1e9).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} Md FCFA`;

function Option({ option }) {
  const payback =
    option.payback_years === null
      ? '—'
      : option.payback_years === 0
        ? 'immédiat'
        : `${option.payback_years.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} ans`;

  return (
    <article className="option card">
      <header className="option-head">
        <h4 className="option-title">{option.name}</h4>
        <span className={`badge badge-${option.risk}`}>
          risque {RISK_LABEL[option.risk] || option.risk}
        </span>
      </header>
      <dl className="option-figures">
        <div><dt>Gain annuel</dt><dd>{milliards(option.risk_adjusted_benefit)}</dd></div>
        <div><dt>Investissement</dt><dd>{milliards(option.capex_xof)}</dd></div>
        <div><dt>Retour</dt><dd>{payback}</dd></div>
        <div><dt>Délai</dt><dd>{option.lead_time_months} mois</dd></div>
      </dl>
      <p className="option-rationale">{option.rationale}</p>
      {option.blocking_conditions.length > 0 && (
        <p className="option-block">
          Bloqué par : {option.blocking_conditions.join(', ')}
        </p>
      )}
    </article>
  );
}

export default function DecisionBoard() {
  const { data, error, loading } = useDataset('decisions');
  const [active, setActive] = useState('sans regret');

  if (loading) return null;
  if (error || !data) return null;

  const current = CATEGORIES.find((c) => c.id === active);
  const key = current.match || current.id;
  const options = data.options.filter((o) => o.category === key);

  return (
    <section className="decisions">
      <div className="section-container">
        <div className="section-header">
          <div className="eyebrow">AIDE À LA DÉCISION</div>
          <h2 className="section-title">Ce que les données imposent</h2>
        </div>

        <ol className="findings">
          {data.findings.map((finding, i) => (
            <li key={i}>{finding}</li>
          ))}
        </ol>

        <div className="tabs">
          {CATEGORIES.map((c) => {
            const count = data.options.filter((o) => o.category === (c.match || c.id)).length;
            return (
              <button
                key={c.id}
                className={`tab ${active === c.id ? 'active' : ''}`}
                onClick={() => setActive(c.id)}
              >
                {c.label} <span className="tab-count">{count}</span>
              </button>
            );
          })}
        </div>
        <p className="tab-blurb">{current.blurb}</p>

        <div className="options-grid">
          {options.map((option) => (
            <Option key={option.id} option={option} />
          ))}
        </div>

        <div className="plan">
          <h3 className="plan-title">Séquence</h3>
          {data.plan.map((step) => (
            <div key={step.horizon} className="plan-step">
              <h4>{step.horizon}</h4>
              <p>{step.logic}</p>
              <p className="plan-figures">
                Gain annuel cumulé {milliards(step.annual_benefit_xof)} — investissement{' '}
                {milliards(step.capex_xof)}.
              </p>
            </div>
          ))}
        </div>
      </div>
      <style>{`
        .decisions { padding: var(--s-12) 0; border-top: 1px solid var(--border-soft); }
        .section-container { max-width: 1200px; margin: 0 auto; padding: 0 var(--s-5); }
        .section-header { margin-bottom: var(--s-6); max-width: 60ch; }
        .section-title { font-size: 32px; color: var(--mal-indigo-950); }
        .findings { max-width: 74ch; margin: 0 0 var(--s-10) var(--s-5); padding: 0; }
        .findings li { margin-bottom: var(--s-4); line-height: 1.6; color: var(--fg-default); }
        .tabs { display: flex; gap: var(--s-2); flex-wrap: wrap; margin-bottom: var(--s-3); }
        .tab { font-family: var(--font-sans); font-size: 14px; font-weight: 600; padding: 8px 14px; border-radius: var(--r-2); border: 1px solid var(--border-soft); background: transparent; cursor: pointer; color: var(--fg-muted); }
        .tab.active { background: var(--mal-indigo-950); color: #fff; border-color: var(--mal-indigo-950); }
        .tab-count { font-family: var(--font-mono); font-size: 11px; opacity: 0.7; margin-left: 4px; }
        .tab-blurb { font-size: 14px; color: var(--fg-muted); margin-bottom: var(--s-6); }
        .options-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--s-5); margin-bottom: var(--s-12); }
        .option { display: flex; flex-direction: column; gap: var(--s-4); }
        .option-head { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--s-3); }
        .option-title { font-size: 19px; line-height: 1.3; }
        .option-figures { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--s-3); margin: 0; }
        .option-figures dt { font-size: 11px; color: var(--fg-muted); text-transform: uppercase; letter-spacing: 0.05em; }
        .option-figures dd { margin: 2px 0 0; font-family: var(--font-mono); font-size: 15px; color: var(--mal-indigo-950); }
        .option-rationale { font-size: 14px; line-height: 1.6; color: var(--fg-muted); }
        .option-block { font-size: 12px; font-family: var(--font-mono); color: #C62828; }
        .badge { font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.06em; text-transform: uppercase; padding: 2px 6px; border-radius: var(--r-1); white-space: nowrap; }
        .badge-faible { background: #E3F1E4; color: #2E7D32; }
        .badge-moyen { background: var(--mal-bone-200); color: var(--mal-indigo-700); }
        .badge-eleve { background: #FBE9E7; color: #C62828; }
        .plan-title { font-size: 24px; margin-bottom: var(--s-5); }
        .plan-step { border-left: 2px solid var(--mal-ochre-500); padding-left: var(--s-5); margin-bottom: var(--s-6); max-width: 74ch; }
        .plan-step h4 { font-size: 17px; margin-bottom: var(--s-2); }
        .plan-step p { font-size: 14px; line-height: 1.6; color: var(--fg-muted); }
        .plan-figures { font-family: var(--font-mono); font-size: 13px; margin-top: var(--s-2); color: var(--mal-indigo-700); }
        @media (max-width: 860px) { .options-grid { grid-template-columns: 1fr; } }
      `}</style>
    </section>
  );
}
