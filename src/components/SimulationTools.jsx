import React, { useState } from 'react';

export const TOOLS = [
  {
    id: 'powerfactory',
    name: 'PowerFactory',
    vendor: 'DIgSILENT GmbH',
    domain: 'power',
    icon: 'ph-lightning',
    license: 'Commerciale',
    language: 'GUI · DPL · Python',
    scale: 'ms → heures (RMS / EMT)',
    tagline: "Référence industrielle pour les études de réseaux de transport et de distribution.",
    capabilities: [
      "Répartition de charge (load flow) équilibrée et déséquilibrée",
      "Court-circuit selon CEI 60909 et méthode complète",
      "Stabilité transitoire RMS et simulation EMT",
      "Coordination des protections et sélectivité",
      "Analyse de contingences (N-1) et harmoniques",
    ],
    mali: "Études de raccordement des producteurs indépendants solaires au réseau interconnecté d'EDM-SA, réglage des protections sur les artères 225 kV et 150 kV, analyse de stabilité en scénario de forte pénétration photovoltaïque.",
    link: 'https://www.digsilent.de/en/powerfactory.html',
  },
  {
    id: 'openmodelica',
    name: 'OpenModelica',
    vendor: 'Open Source Modelica Consortium',
    domain: 'multi',
    icon: 'ph-circuitry',
    license: 'Open source (OSMC-PL / GPL)',
    language: 'Modelica · Python · OMShell',
    scale: 'µs → années',
    tagline: "Modélisation multi-physique acausale : électricité, thermique, mécanique, fluides dans un même modèle.",
    capabilities: [
      "Langage Modelica orienté équations, non causal",
      "Bibliothèques PowerSystems, Buildings, ThermoPower",
      "Co-simulation et export FMI / FMU",
      "Optimisation dynamique et analyse de sensibilité",
      "Chaîne entièrement libre, sans coût de licence",
    ],
    mali: "Dimensionnement des mini-réseaux hybrides villageois PV–diesel–batterie, modélisation du comportement thermique des bâtiments et du séchage solaire agricole, formation universitaire sans barrière de licence.",
    link: 'https://openmodelica.org/',
  },
  {
    id: 'pandapower',
    name: 'pandapower',
    vendor: 'Université de Kassel · Fraunhofer IEE',
    domain: 'power',
    icon: 'ph-graph',
    license: 'Open source (BSD-3)',
    language: 'Python',
    scale: 'Régime permanent · séries temporelles',
    tagline: "Analyse de réseaux électriques scriptable, pensée pour l'automatisation et les grands jeux de données.",
    capabilities: [
      "Load flow Newton-Raphson et backward/forward sweep",
      "Optimal power flow (OPF) et estimation d'état",
      "Court-circuit CEI 60909 simplifié",
      "Simulations chronologiques sur profils annuels",
      "Structures de données pandas, intégration GIS et CSV",
    ],
    mali: "Traitement par lots des départs MT/BT de Bamako, quantification des pertes techniques, planification de l'électrification rurale à partir des couches SIG existantes.",
    link: 'https://www.pandapower.org/',
  },
  {
    id: 'pandapipes',
    name: 'pandapipes',
    vendor: 'Fraunhofer IEE',
    domain: 'fluid',
    icon: 'ph-drop',
    license: 'Open source (BSD-3)',
    language: 'Python',
    scale: 'Régime permanent · transitoire lent',
    tagline: "Le pendant fluides de pandapower : eau, gaz, chaleur et hydrogène.",
    capabilities: [
      "Calcul hydraulique des réseaux d'eau et de gaz",
      "Réseaux de chaleur avec bilan thermique",
      "Fluides personnalisables, dont l'hydrogène",
      "Couplage sectoriel direct avec pandapower",
      "Même logique d'API que pandapower",
    ],
    mali: "Réseaux d'adduction d'eau potable et arbitrage entre pompage solaire et pompage sur réseau, études de couplage eau–énergie, préparation des futurs projets d'hydrogène vert.",
    link: 'https://www.pandapipes.org/',
  },
  {
    id: 'simscape',
    name: 'Simscape Electrical',
    vendor: 'MathWorks',
    domain: 'multi',
    icon: 'ph-waveform',
    license: 'Commerciale (MATLAB / Simulink)',
    language: 'Simulink · MATLAB',
    scale: 'µs → minutes (EMT)',
    tagline: "Électronique de puissance et lois de commande, jusqu'à la simulation temps réel.",
    capabilities: [
      "Modèles détaillés d'onduleurs et de convertisseurs",
      "Conception et réglage des boucles de régulation",
      "Simulation EMT à pas fixe pour temps réel",
      "Génération de code pour bancs HIL",
      "Couplage avec l'écosystème MATLAB (identification, optimisation)",
    ],
    mali: "Conception de la commande des onduleurs de mini-réseaux, validation sur banc hardware-in-the-loop avant déploiement en brousse, étude du comportement des groupes hybrides en îlotage.",
    link: 'https://www.mathworks.com/products/simscape-electrical.html',
  },
];

const FILTERS = [
  { id: 'all', label: 'Tous les outils' },
  { id: 'power', label: 'Réseaux électriques' },
  { id: 'multi', label: 'Multi-physique' },
  { id: 'fluid', label: 'Réseaux de fluides' },
];

const WORKFLOW = [
  { step: '01', title: 'Cadrer', tools: 'pandapower', desc: "Construire le modèle du réseau, chiffrer les pertes et tester des dizaines de variantes par script." },
  { step: '02', title: 'Valider', tools: 'PowerFactory', desc: "Reprendre le scénario retenu pour les études normatives exigées par le gestionnaire de réseau." },
  { step: '03', title: 'Dynamiser', tools: 'OpenModelica · Simscape Electrical', desc: "Descendre à l'échelle de la milliseconde : commande des convertisseurs, îlotage, stabilité." },
  { step: '04', title: 'Coupler', tools: 'pandapipes', desc: "Relier le réseau électrique aux réseaux d'eau, de gaz et de chaleur pour les projets multi-énergies." },
];

export default function SimulationTools() {
  const [filter, setFilter] = useState('all');
  const [openId, setOpenId] = useState(TOOLS[0].id);

  const visible = filter === 'all' ? TOOLS : TOOLS.filter((t) => t.domain === filter);

  return (
    <section className="sim">
      <div className="section-container">
        <div className="sim-header">
          <div className="eyebrow">Ingénierie · Outils de simulation</div>
          <h2 className="sim-title">Simuler le système énergétique malien</h2>
          <p className="sim-dek">
            Cinq environnements couvrent l{'’'}essentiel des besoins de modélisation du secteur, de la planification
            des départs basse tension à la commande des onduleurs. Deux sont commerciaux, trois sont libres et
            utilisables sans budget de licence.
          </p>
        </div>

        <div className="sim-filters" role="tablist" aria-label="Filtrer par domaine">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              role="tab"
              aria-selected={filter === f.id}
              className={`chip ${filter === f.id ? 'chip-active' : ''}`}
              onClick={() => setFilter(f.id)}
            >
              {f.label}
            </button>
          ))}
        </div>

        <div className="sim-grid">
          {visible.map((t) => {
            const open = openId === t.id;
            return (
              <article key={t.id} className={`sim-card card ${open ? 'sim-card-open' : ''}`}>
                <header className="sim-card-head">
                  <div className="sim-icon"><i className={`ph ${t.icon}`}></i></div>
                  <div>
                    <h3 className="sim-name">{t.name}</h3>
                    <div className="sim-vendor">{t.vendor}</div>
                  </div>
                  <span className={`sim-badge ${t.license.startsWith('Open') ? 'is-open' : 'is-commercial'}`}>
                    {t.license.startsWith('Open') ? 'Libre' : 'Commercial'}
                  </span>
                </header>

                <p className="sim-tagline">{t.tagline}</p>

                <dl className="sim-meta">
                  <div><dt>Licence</dt><dd>{t.license}</dd></div>
                  <div><dt>Interface</dt><dd>{t.language}</dd></div>
                  <div><dt>Échelle</dt><dd>{t.scale}</dd></div>
                </dl>

                <button
                  className="sim-toggle"
                  aria-expanded={open}
                  onClick={() => setOpenId(open ? null : t.id)}
                >
                  {open ? 'Masquer le détail' : 'Voir capacités et usages'}
                  <span className="sim-caret">{open ? '↑' : '↓'}</span>
                </button>

                {open && (
                  <div className="sim-detail">
                    <h4 className="sim-sub">Capacités</h4>
                    <ul className="sim-list">
                      {t.capabilities.map((c, i) => <li key={i}>{c}</li>)}
                    </ul>
                    <h4 className="sim-sub">Au Mali</h4>
                    <p className="sim-mali">{t.mali}</p>
                    <a className="sim-link" href={t.link} target="_blank" rel="noreferrer">
                      Documentation officielle →
                    </a>
                  </div>
                )}
              </article>
            );
          })}
        </div>

        <div className="sim-table-wrap">
          <h3 className="sim-section-title">Comparatif</h3>
          <table className="sim-table">
            <thead>
              <tr>
                <th scope="col">Outil</th>
                <th scope="col">Domaine</th>
                <th scope="col">Licence</th>
                <th scope="col">Interface</th>
                <th scope="col">Échelle de temps</th>
              </tr>
            </thead>
            <tbody>
              {TOOLS.map((t) => (
                <tr key={t.id}>
                  <th scope="row">{t.name}</th>
                  <td>{FILTERS.find((f) => f.id === t.domain).label}</td>
                  <td>{t.license}</td>
                  <td>{t.language}</td>
                  <td>{t.scale}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="sim-workflow">
          <h3 className="sim-section-title">Une chaîne d{'’'}outils, pas un outil unique</h3>
          <div className="sim-steps">
            {WORKFLOW.map((w) => (
              <div key={w.step} className="sim-step">
                <div className="sim-step-num">{w.step}</div>
                <h4 className="sim-step-title">{w.title}</h4>
                <div className="sim-step-tools">{w.tools}</div>
                <p className="sim-step-desc">{w.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <style>{`
        .sim { padding: var(--s-12) 0; }
        .section-container { max-width: 1200px; margin: 0 auto; padding: 0 var(--s-5); }
        .sim-header { max-width: 68ch; margin-bottom: var(--s-6); }
        .sim-title { font-size: 32px; color: var(--mal-indigo-950); margin-bottom: var(--s-3); }
        .sim-dek { color: var(--fg-muted); font-size: 17px; }

        .sim-filters { display: flex; flex-wrap: wrap; gap: var(--s-2); margin-bottom: var(--s-6); }
        .chip {
          font-family: var(--font-sans); font-size: 13px; font-weight: 500;
          padding: var(--s-1) var(--s-3); border-radius: var(--r-pill);
          border: 1px solid var(--border-soft); background: var(--bg-surface);
          color: var(--fg-muted); cursor: pointer; transition: 0.2s;
        }
        .chip:hover { color: var(--mal-indigo-700); border-color: var(--mal-indigo-500); }
        .chip-active { background: var(--mal-indigo-700); border-color: var(--mal-indigo-700); color: #fff; }

        .sim-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--s-5); align-items: start; }
        .sim-card { display: flex; flex-direction: column; gap: var(--s-4); }
        .sim-card-open { border-color: var(--mal-indigo-500); }
        .sim-card-head { display: grid; grid-template-columns: 40px 1fr auto; gap: var(--s-3); align-items: center; }
        .sim-icon {
          width: 40px; height: 40px; border-radius: var(--r-2); background: var(--mal-bone-200);
          display: flex; align-items: center; justify-content: center;
          font-size: 20px; color: var(--mal-indigo-700);
        }
        .sim-name { font-size: 20px; }
        .sim-vendor { font-family: var(--font-mono); font-size: 11px; color: var(--fg-muted); }
        .sim-badge {
          font-family: var(--font-mono); font-size: 10px; font-weight: 600; letter-spacing: 0.08em;
          text-transform: uppercase; padding: var(--s-1) var(--s-2); border-radius: var(--r-pill);
        }
        .sim-badge.is-open { background: rgba(110, 138, 111, 0.18); color: var(--mal-sage-700); }
        .sim-badge.is-commercial { background: rgba(208, 109, 89, 0.18); color: var(--mal-clay-900); }
        .sim-tagline { font-size: 15px; color: var(--fg-muted); }

        .sim-meta { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--s-3); border-top: 1px solid var(--border-soft); padding-top: var(--s-4); }
        .sim-meta dt { font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--fg-accent); font-weight: 600; }
        .sim-meta dd { font-family: var(--font-mono); font-size: 12px; color: var(--fg-main); margin-top: var(--s-1); }

        .sim-toggle {
          margin-top: auto; align-self: flex-start; display: inline-flex; align-items: center; gap: var(--s-2);
          background: none; border: none; padding: 0; cursor: pointer;
          font-family: var(--font-sans); font-size: 14px; font-weight: 600; color: var(--fg-link);
        }
        .sim-toggle:hover { color: var(--mal-ochre-700); }
        .sim-caret { font-size: 12px; }

        .sim-detail { border-top: 1px solid var(--border-soft); padding-top: var(--s-4); }
        .sim-sub { font-family: var(--font-sans); font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: var(--fg-muted); margin-bottom: var(--s-2); }
        .sim-list { margin: 0 0 var(--s-4) var(--s-4); font-size: 14px; }
        .sim-list li { margin-bottom: var(--s-1); }
        .sim-mali { font-size: 14px; color: var(--fg-muted); margin-bottom: var(--s-4); }
        .sim-link { font-size: 14px; font-weight: 600; text-decoration: none; }

        .sim-section-title { font-size: 24px; color: var(--mal-indigo-950); margin-bottom: var(--s-5); }
        .sim-table-wrap { margin-top: var(--s-12); overflow-x: auto; }
        .sim-table { width: 100%; border-collapse: collapse; font-size: 14px; background: var(--bg-surface); border: 1px solid var(--border-soft); border-radius: var(--r-2); }
        .sim-table th, .sim-table td { text-align: left; padding: var(--s-3) var(--s-4); border-bottom: 1px solid var(--border-soft); }
        .sim-table thead th {
          font-family: var(--font-sans); font-size: 11px; font-weight: 700; text-transform: uppercase;
          letter-spacing: 0.1em; color: var(--fg-muted); background: var(--bg-sunken);
        }
        .sim-table tbody th { font-family: var(--font-sans); font-weight: 600; color: var(--mal-indigo-950); }
        .sim-table td { font-family: var(--font-mono); font-size: 12px; color: var(--fg-muted); }
        .sim-table tbody tr:last-child th, .sim-table tbody tr:last-child td { border-bottom: none; }

        .sim-workflow { margin-top: var(--s-12); }
        .sim-steps { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--s-5); }
        .sim-step { border-top: 2px solid var(--mal-ochre-600); padding-top: var(--s-4); }
        .sim-step-num { font-family: var(--font-mono); font-size: 12px; color: var(--fg-accent); margin-bottom: var(--s-2); }
        .sim-step-title { font-size: 20px; margin-bottom: var(--s-1); }
        .sim-step-tools { font-family: var(--font-mono); font-size: 11px; color: var(--mal-indigo-700); margin-bottom: var(--s-3); }
        .sim-step-desc { font-size: 14px; color: var(--fg-muted); }

        @media (max-width: 900px) {
          .sim-grid { grid-template-columns: 1fr; }
          .sim-steps { grid-template-columns: repeat(2, 1fr); }
        }
        @media (max-width: 560px) {
          .sim-steps { grid-template-columns: 1fr; }
          .sim-meta { grid-template-columns: 1fr; }
        }
      `}</style>
    </section>
  );
}
