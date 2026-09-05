import { useEffect, useState } from 'react';

/**
 * Charge un document JSON produit par `python -m malinergy export`.
 *
 * Le site n'inscrit aucun chiffre en dur : toute valeur affichée provient de
 * `public/data/`, ce qui garantit qu'une correction dans `malinergy/data`
 * se propage à la page sans édition manuelle.
 */
export default function useDataset(name) {
  const [state, setState] = useState({ data: null, error: null, loading: true });

  useEffect(() => {
    let cancelled = false;
    const base = import.meta.env.BASE_URL || '/';

    fetch(`${base}data/${name}.json`)
      .then((response) => {
        if (!response.ok) throw new Error(`${name}.json indisponible (${response.status})`);
        return response.json();
      })
      .then((document) => {
        if (!cancelled) {
          setState({ data: document.data, error: null, loading: false, snapshot: document.snapshot });
        }
      })
      .catch((error) => {
        if (!cancelled) setState({ data: null, error, loading: false });
      });

    return () => { cancelled = true; };
  }, [name]);

  return state;
}
