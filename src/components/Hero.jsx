import React from 'react';

export default function Hero() {
  return (
    <section className="hero">
      <div className="hero-container">
        <div className="hero-content">
          <div className="eyebrow">Journal de bord · Énergie · Mali</div>
          <h1 className="hero-title">
            Malinergy : Comprendre l{'\u0027'}énergie au Mali, des données à la gouvernance.
          </h1>
          <p className="hero-dek">
            Une plateforme de connaissances pour tout ce qui concerne l'énergie au Mali — économie, ingénierie, actualités, gouvernance, communauté.
          </p>
          <div className="hero-actions">
            <button className="btn btn-primary">Lire les analyses</button>
            <button className="btn btn-secondary">Explorer les données</button>
          </div>
        </div>
        <div className="hero-visual">
          <div className="hero-image-container">
             <div className="hero-image-placeholder">
                <i className="ph ph-lightning-fill" style={{fontSize: 64, color: 'var(--mal-ochre-500)'}}></i>
             </div>
             <div className="bogolan-overlay"></div>
          </div>
        </div>
      </div>
      <style>{`
        .hero {
          padding: var(--s-12) 0;
          background-color: var(--bg-page);
          overflow: hidden;
        }
        .hero-container {
          max-width: 1200px;
          margin: 0 auto;
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: var(--s-10);
          align-items: center;
          padding: 0 var(--s-5);
        }
        .hero-title {
          font-size: 48px;
          margin-bottom: var(--s-5);
          color: var(--mal-indigo-950);
          line-height: 1.1;
        }
        .hero-dek {
          font-size: 18px;
          color: var(--fg-muted);
          margin-bottom: var(--s-8);
          max-width: 45ch;
        }
        .hero-actions {
          display: flex;
          gap: var(--s-4);
        }
        .hero-image-container {
          position: relative;
          aspect-ratio: 4/3;
          background: var(--mal-indigo-900);
          border-radius: var(--r-3);
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: var(--shadow-3);
        }
        .hero-image-placeholder {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: var(--s-4);
        }
        .bogolan-overlay {
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          mask: url('/assets/bogolan-tile.svg') repeat;
          -webkit-mask: url('/assets/bogolan-tile.svg') repeat;
          opacity: 0.1;
        }
      `}</style>
    </section>
  );
}
