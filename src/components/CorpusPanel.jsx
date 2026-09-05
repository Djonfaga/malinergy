import React, { useState } from 'react';
import useDataset from '../hooks/useDataset';

const nombre = (v, digits = 0) =>
  v.toLocaleString('fr-FR', { maximumFractionDigits: digits });

function Reconciliation({ rows, score }) {
  return (
    <div className="recon">
      <div className="recon-head">
        <h3 className="sub-title">Confrontation aux sources publiées</h3>
        <span className="score">Concordance {Math.round(score * 100)} %</span>
      </div>
      <p className="sub-dek">
        Chaque grandeur calculée par la plateforme est confrontée à la valeur publiée
        correspondante. Les écarts sont affichés, pas lissés : un écart signalé est une
        question ouverte, un écart corrigé en silence est une erreur cachée.
      </p>
      <div className="recon-table" role="table">
        <div className="recon-row recon-header" role="row">
          <span>Grandeur</span><span>Publiée</span><span>Malinergy</span><span>Écart</span>
        </div>
        {rows.map((r) => (
          <div key={r.observation} className={`recon-row ${r.agrees ? 'ok' : 'gap'}`} role="row">
            <span className="recon-label">
              {r.label}
              {r.resolution && <em className="recon-note">{r.resolution}</em>}
            </span>
            <span className="mono">{nombre(r.published, 2)}</span>
            <span className="mono">{nombre(r.internal, 2)}</span>
            <span className="mono gapv">
              {r.relative_gap > 0 ? '+' : ''}{(r.relative_gap * 100).toFixed(1)} %
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function CorpusPanel() {
  const { data, loading, error } = useDataset('corpus');
  const [showAll, setShowAll] = useState(false);

  if (loading || error || !data) return null;

  const { coverage, observations, reconciliation, score } = data;
  const gap = data.energy_poverty_gap;
  const inequity = data.tariff_inequity;
  const captive = data.captive_capacity;
  const security = data.fuel_security;
  const shown = showAll ? observations : observations.slice(0, 12);

  return (
    <section className="corpus">
      <div className="section-container">
        <div className="section-header">
          <div className="eyebrow">CORPUS EXTERNE</div>
          <h2 className="section-title">Ce que le reste du monde publie sur l{'’'}énergie malienne</h2>
          <p className="section-dek">
            {coverage.count} observations issues de {coverage.distinct_sources} sources,
            de {coverage.year_span[0]} à {coverage.year_span[1]}. Une partie vient de jeux de
            données mondiaux où le Mali n{'’'}est qu{'’'}une ligne parmi deux cents pays.
          </p>
        </div>

        <div className="facts">
          <div className="fact card">
            <div className="fact-value">{nombre(gap.comparators['Afrique'].multiple, 1)}×</div>
            <div className="fact-label">
              L{'’'}écart à la moyenne africaine de consommation par habitant
              ({nombre(gap.mali_kwh_per_capita)} kWh contre {nombre(gap.comparators['Afrique'].kwh_per_capita)})
            </div>
          </div>
          <div className="fact card">
            <div className="fact-value">{nombre(inequity.ratio_mini_grid_to_grid, 1)}×</div>
            <div className="fact-label">
              Ce que paie un ménage de mini-réseau rural
              ({nombre(inequity.mini_grid_xof_per_kwh)} FCFA/kWh) par rapport à un abonné du
              réseau, sans recevoir de subvention
            </div>
          </div>
          <div className="fact card">
            <div className="fact-value">{nombre(captive.total_operating_mw)} MW</div>
            <div className="fact-label">
              Autoproduction des mines d{'’'}or, soit {Math.round(captive.ratio_to_edm_thermal * 100)} %
              du thermique d{'’'}EDM-SA, dont {nombre(captive.operating_solar_mw)} MW solaire
            </div>
          </div>
          <div className="fact card">
            <div className="fact-value">{Math.round(security.share_of_firm_capacity * 100)} %</div>
            <div className="fact-label">
              De la puissance ferme dépend d{'’'}un carburant acheminé par route —
              {' '}{nombre(security.trucks_destroyed)} camions-citernes détruits depuis
              septembre 2025
            </div>
          </div>
        </div>

        <Reconciliation rows={reconciliation} score={score} />

        <h3 className="sub-title">Observations collectées</h3>
        <div className="obs-grid">
          {shown.map((o) => (
            <div key={o.id} className="obs">
              <span className="obs-label">{o.label}</span>
              <span className="obs-value mono">
                {nombre(o.value, 2)} <em>{o.unit}</em>
              </span>
              <span className="obs-meta">{o.scope} · {o.year} · {o.source}</span>
            </div>
          ))}
        </div>
        <div className="actions">
          {observations.length > 12 && (
            <button className="more" onClick={() => setShowAll(!showAll)}>
              {showAll ? 'Réduire' : `Voir les ${observations.length} observations`}
            </button>
          )}
          <a className="more download" href="assets/malinergy-rapport.pdf" download>
            Télécharger le rapport de décision (PDF)
          </a>
        </div>
      </div>
      <style>{`
        .corpus { padding: var(--s-12) 0; background: var(--bg-sunken); }
        .section-container { max-width: 1200px; margin: 0 auto; padding: 0 var(--s-5); }
        .section-header { margin-bottom: var(--s-8); max-width: 62ch; }
        .section-title { font-size: 32px; color: var(--mal-indigo-950); margin-bottom: var(--s-3); }
        .section-dek { color: var(--fg-muted); font-size: 15px; line-height: 1.6; }
        .sub-title { font-size: 20px; margin: var(--s-10) 0 var(--s-2); }
        .sub-dek { font-size: 14px; color: var(--fg-muted); max-width: 70ch; margin-bottom: var(--s-5); line-height: 1.6; }
        .mono { font-family: var(--font-mono); }
        .facts { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--s-5); }
        .fact { display: flex; flex-direction: column; gap: var(--s-3); }
        .fact-value { font-family: var(--font-mono); font-size: 30px; font-weight: 600; color: var(--mal-clay-700); }
        .fact-label { font-size: 13px; line-height: 1.5; color: var(--fg-muted); }
        .recon-head { display: flex; align-items: baseline; justify-content: space-between; gap: var(--s-4); }
        .score { font-family: var(--font-mono); font-size: 12px; padding: 3px 8px; border-radius: var(--r-1); background: #E3F1E4; color: #2E7D32; }
        .recon-table { border: 1px solid var(--border-soft); border-radius: var(--r-2); overflow: hidden; background: #fff; }
        .recon-row { display: grid; grid-template-columns: 3fr 1fr 1fr 0.7fr; gap: var(--s-4); padding: var(--s-3) var(--s-4); font-size: 14px; align-items: start; }
        .recon-row + .recon-row { border-top: 1px solid var(--border-soft); }
        .recon-header { font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--fg-muted); background: var(--mal-bone-200); }
        .recon-row.gap .gapv { color: #C62828; font-weight: 600; }
        .recon-row.ok .gapv { color: #2E7D32; }
        .recon-label { display: flex; flex-direction: column; gap: 4px; }
        .recon-note { font-style: normal; font-size: 12px; color: var(--fg-muted); line-height: 1.5; }
        .obs-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--s-4); }
        .obs { display: flex; flex-direction: column; gap: 3px; padding: var(--s-3) var(--s-4); background: #fff; border: 1px solid var(--border-soft); border-radius: var(--r-2); }
        .obs-label { font-size: 13px; line-height: 1.4; }
        .obs-value { font-size: 17px; color: var(--mal-indigo-950); }
        .obs-value em { font-style: normal; font-size: 11px; color: var(--fg-muted); }
        .obs-meta { font-family: var(--font-mono); font-size: 10px; color: var(--fg-muted); }
        .actions { display: flex; gap: var(--s-3); flex-wrap: wrap; margin-top: var(--s-5); }
        .more {  font-family: var(--font-sans); font-size: 14px; font-weight: 600; padding: 8px 14px; border-radius: var(--r-2); border: 1px solid var(--border-soft); background: transparent; cursor: pointer; color: var(--mal-indigo-700); text-decoration: none; display: inline-block; }
        .download { background: var(--mal-indigo-950); color: #fff; border-color: var(--mal-indigo-950); }
        @media (max-width: 1000px) { .facts { grid-template-columns: repeat(2, 1fr); } .obs-grid { grid-template-columns: repeat(2, 1fr); } }
        @media (max-width: 640px) { .facts, .obs-grid { grid-template-columns: 1fr; } .recon-row { grid-template-columns: 1fr; gap: 4px; } }
      `}</style>
    </section>
  );
}
