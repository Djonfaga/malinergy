import React from 'react';

export function Pillars({ setRoute }) {
  const pillars = [
    { id: 'econ', title: 'Économie', icon: 'ph-coins', desc: 'Tarifs, EDM-SA, investissements.' },
    { id: 'eng', title: 'Ingénierie', icon: 'ph-gear', desc: 'Centrales, réseaux, technique.' },
    { id: 'gov', title: 'Gouvernance', icon: 'ph-bank', desc: 'Régulation, lois, acteurs.' },
    { id: 'data', title: 'Données', icon: 'ph-database', desc: 'Séries temporelles, cartes.' },
  ];

  return (
    <section className="pillars">
      <div className="section-container">
         <div className="pillars-grid">
            {pillars.map(p => (
              <div key={p.id} className="pillar-item card" onClick={() => setRoute(p.id)}>
                <i className={`ph ${p.icon} pillar-icon`}></i>
                <h3 className="pillar-title">{p.title}</h3>
                <p className="pillar-desc">{p.desc}</p>
                <div className="pillar-arrow">→</div>
              </div>
            ))}
         </div>
      </div>
      <style>{`
        .pillars { padding: var(--s-12) 0; border-top: 1px solid var(--border-soft); }
        .pillars-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--s-5); }
        .pillar-item { cursor: pointer; position: relative; }
        .pillar-icon { font-size: 24px; color: var(--mal-ochre-700); margin-bottom: var(--s-3); display: block; }
        .pillar-title { margin-bottom: var(--s-2); font-size: 20px; }
        .pillar-desc { font-size: 14px; color: var(--fg-muted); }
        .pillar-arrow { position: absolute; bottom: var(--s-5); right: var(--s-5); opacity: 0; transition: 0.2s; color: var(--mal-indigo-700); }
        .pillar-item:hover .pillar-arrow { opacity: 1; transform: translateX(4px); }
      `}</style>
    </section>
  );
}

export function LatestGrid() {
  const articles = [
    { title: "La nouvelle centrale de Sikasso entre en service", category: "PROJETS", date: "12 Avril" },
    { title: "Analyse : Pourquoi le tarif social ne suffit plus", category: "ÉCONOMIE", date: "10 Avril" },
    { title: "Rapport CREE : Performance des mini-réseaux 2025", category: "GOUVERNANCE", date: "08 Avril" },
  ];

  return (
    <section className="latest">
      <div className="section-container">
        <div className="eyebrow">Dernières publications</div>
        <div className="latest-grid">
          {articles.map((a, i) => (
            <article key={i} className="article-card card">
               <div className="article-meta">
                  <span className="article-cat">{a.category}</span>
                  <span className="article-date">{a.date}</span>
               </div>
               <h2 className="article-title">{a.title}</h2>
               <a href="#" className="article-link">Lire la suite →</a>
            </article>
          ))}
        </div>
      </div>
      <style>{`
        .latest { padding: var(--s-12) 0; }
        .latest-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--s-5); margin-top: var(--s-6); }
        .article-card { display: flex; flex-direction: column; gap: var(--s-4); }
        .article-meta { display: flex; justify-content: space-between; font-family: var(--font-mono); font-size: 11px; color: var(--fg-muted); }
        .article-cat { color: var(--mal-clay-700); font-weight: 600; }
        .article-title { font-size: 22px; line-height: 1.3; }
        .article-link { margin-top: auto; font-size: 14px; font-weight: 600; text-decoration: none; }
      `}</style>
    </section>
  );
}

export function Footer() {
  return (
    <footer className="footer">
      <div className="section-container">
        <div className="footer-grid">
          <div className="footer-brand">
            <div className="logo">
               <span className="logo-text">Malinergy</span>
            </div>
            <p className="footer-tagline">Le journal de record du secteur énergétique malien.</p>
          </div>
          <div className="footer-links">
            <h4 className="footer-heading">Plateforme</h4>
            <ul>
              <li><a href="#">À propos</a></li>
              <li><a href="#">Équipe</a></li>
              <li><a href="#">Méthodologie</a></li>
              <li><a href="#">Contact</a></li>
            </ul>
          </div>
          <div className="footer-links">
            <h4 className="footer-heading">Légal</h4>
            <ul>
              <li><a href="#">Confidentialité</a></li>
              <li><a href="#">Conditions</a></li>
              <li><a href="#">Licence CC-BY 4.0</a></li>
            </ul>
          </div>
        </div>
        <div className="footer-bottom">
          <p>© 2026 Malinergy. Tous droits réservés.</p>
        </div>
      </div>
      <style>{`
        .footer { background: var(--mal-indigo-950); color: white; padding: var(--s-12) 0 var(--s-6); }
        .footer-grid { display: grid; grid-template-columns: 2fr 1fr 1fr; gap: var(--s-10); margin-bottom: var(--s-12); }
        .footer-tagline { margin-top: var(--s-4); color: var(--mal-bone-300); opacity: 0.7; max-width: 30ch; }
        .footer-heading { color: var(--mal-ochre-500); text-transform: uppercase; letter-spacing: 0.1em; font-size: 12px; margin-bottom: var(--s-4); font-family: var(--font-sans); font-weight: 700; }
        .footer-links ul { list-style: none; }
        .footer-links li { margin-bottom: var(--s-2); }
        .footer-links a { color: white; text-decoration: none; opacity: 0.8; font-size: 14px; }
        .footer-links a:hover { opacity: 1; color: var(--mal-ochre-500); }
        .footer-bottom { border-top: 1px solid rgba(255,255,255,0.1); padding-top: var(--s-6); font-size: 12px; color: var(--mal-bone-300); opacity: 0.5; }
        .section-container { max-width: 1200px; margin: 0 auto; padding: 0 var(--s-5); }
      `}</style>
    </footer>
  );
}
