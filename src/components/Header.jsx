import React from 'react';

export default function Header({ route, setRoute }) {
  const navItems = [
    { id: 'home', label: 'Accueil' },
    { id: 'data', label: 'Données' },
    { id: 'econ', label: 'Économie' },
    { id: 'eng', label: 'Ingénierie' },
    { id: 'gov', label: 'Gouvernance' },
  ];

  return (
    <header className="header">
      <div className="header-container">
        <div className="logo" onClick={() => setRoute('home')}>
          <div className="logo-mark"></div>
          <span className="logo-text">Malinergy</span>
        </div>
        <nav className="nav">
          {navItems.map((item) => (
            <button
              key={item.id}
              className={`nav-link ${route === item.id ? 'active' : ''}`}
              onClick={() => setRoute(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <div className="header-actions">
          <button className="btn btn-secondary btn-sm">FR / EN</button>
          <button className="btn btn-primary btn-sm">S'abonner</button>
        </div>
      </div>
      <style>{`
        .header {
          position: sticky;
          top: 0;
          z-index: 100;
          background: rgba(251, 248, 242, 0.85);
          backdrop-filter: blur(8px);
          border-bottom: 1px solid var(--border-soft);
          padding: var(--s-3) 0;
        }
        .header-container {
          max-width: 1200px;
          margin: 0 auto;
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 0 var(--s-5);
        }
        .logo {
          display: flex;
          align-items: center;
          gap: var(--s-2);
          cursor: pointer;
        }
        .logo-text {
          font-family: var(--font-serif);
          font-size: 20px;
          font-weight: 600;
          color: var(--mal-indigo-950);
        }
        .logo-mark {
          width: 32px;
          height: 32px;
          background: var(--mal-ochre-600);
          mask: url('/assets/logo-mark.svg') no-repeat center;
          -webkit-mask: url('/assets/logo-mark.svg') no-repeat center;
          mask-size: contain;
          -webkit-mask-size: contain;
        }
        .nav {
          display: flex;
          gap: var(--s-5);
        }
        .nav-link {
          background: none;
          border: none;
          font-family: var(--font-sans);
          font-size: 14px;
          font-weight: 500;
          color: var(--fg-muted);
          cursor: pointer;
          padding: var(--s-1) 0;
          position: relative;
          transition: color 0.2s;
        }
        .nav-link:hover, .nav-link.active {
          color: var(--mal-indigo-700);
        }
        .nav-link.active::after {
          content: '';
          position: absolute;
          bottom: -4px;
          left: 0;
          width: 100%;
          height: 2px;
          background: var(--mal-ochre-600);
        }
        .btn-sm {
          padding: var(--s-1) var(--s-3);
          font-size: 12px;
        }
        .header-actions {
          display: flex;
          gap: var(--s-3);
        }
      `}</style>
    </header>
  );
}
