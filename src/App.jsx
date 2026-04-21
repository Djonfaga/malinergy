import React, { useState } from 'react';
import Header from './components/Header';
import Hero from './components/Hero';
import DataPanel from './components/DataPanel';
import { Pillars, LatestGrid, Footer } from './components/Sections';
import './styles/colors_and_type.css';

function Subpage({ route, setRoute }) {
  const map = {
    data: { eyebrow: 'Données',     h1: "Les données ouvertes de l'énergie malienne", dek: 'Production, capacité, pertes, accès, tarifs. Mises à jour mensuelles. Téléchargeables en CSV.' },
    econ: { eyebrow: 'Économie',    h1: "Comprendre l'économie du secteur", dek: 'Tarifs, subventions, importations, investissements, financements publics et privés.' },
    eng:  { eyebrow: 'Ingénierie',  h1: 'Production, réseau, technologies', dek: 'Panorama technique du système électrique malien, des centrales aux mini-réseaux villageois.' },
    gov:  { eyebrow: 'Gouvernance', h1: 'Régulateurs, ministères, réformes', dek: 'Cartographie des institutions, textes en vigueur, décisions récentes de la CREE.' },
  };
  const p = map[route] || map.data;
  return (
    <div className="subpage" style={{padding: 'var(--s-12) var(--s-5)', maxWidth: 1200, margin: '0 auto'}}>
      <div className="eyebrow">{p.eyebrow}</div>
      <h1 style={{fontSize: 40, marginBottom: 'var(--s-5)'}}>{p.h1}</h1>
      <p className="lead" style={{fontSize: 20, color: 'var(--fg-muted)', maxWidth: '60ch', marginBottom: 'var(--s-8)'}}>{p.dek}</p>
      <div style={{display:'flex', gap:12}}>
        <button className="btn btn-primary" onClick={()=>setRoute('home')}>← Retour à l{'\u2019'}accueil</button>
        <button className="btn btn-secondary">S'abonner à cette rubrique</button>
      </div>
    </div>
  );
}

function App() {
  const [route, setRoute] = useState('home');

  return (
    <div className="site">
      <Header route={route} setRoute={setRoute}/>
      <main>
        {route === 'home' ? (
          <>
            <Hero />
            <Pillars setRoute={setRoute}/>
            <LatestGrid />
            <DataPanel />
          </>
        ) : (
          <Subpage route={route} setRoute={setRoute}/>
        )}
      </main>
      <Footer />
      <style>{`
        .site {
          min-height: 100vh;
          display: flex;
          flex-direction: column;
        }
        main {
          flex: 1;
        }
      `}</style>
    </div>
  );
}

export default App;
