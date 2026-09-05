# Malinergy — l'énergie au Mali

> Plateforme de connaissances ouverte sur le secteur énergétique malien : une base de
> données sourcée, une couche d'analyse qui en tire des conclusions décisionnelles, et un
> site qui publie les deux.

Malinergy documente la structure tarifaire d'EDM-SA et l'organisation du marché, la
topologie du réseau, l'irradiation solaire, l'historique du délestage et la séquence des
réformes du secteur — puis s'en sert pour répondre à une question précise : **au vu de ces
données, quelles décisions de développement énergétique tiennent debout, dans quel ordre,
et sous quelles conditions ?**

## La règle du dépôt

Aucune valeur chiffrée ne vit dans le code. Tout nombre est stocké dans
`malinergy/data/*.json` et porte un identifiant de source déclaré dans
`malinergy/data/sources.json`. Le chargement échoue si une référence manque.

Trois conséquences, qui sont l'intérêt principal du projet :

1. Corriger une donnée suffit à recalculer toutes les conclusions — rapport et site
   compris — sans toucher à une ligne de calcul.
2. Chaque chiffre publié affiche son niveau de confiance. Les estimations Malinergy sont
   signalées comme telles et ne sont jamais présentées comme des relevés officiels.
3. Aucune option d'action ne peut être avantagée par un chiffre posé d'autorité : le
   bénéfice de chaque option est recalculé à partir des jeux de données.

## Ce que la couche d'analyse calcule

| Module | Question traitée |
|---|---|
| `analysis/tariff.py` | Ce que paie réellement un abonné, l'écart entre le tarif et le coût de fourniture, et qui capte la subvention |
| `analysis/dispatch.py` | L'ordre de mérite du parc, le coût marginal, l'équilibre de puissance ferme, la valeur d'un kWh économisé |
| `analysis/lcoe.py` | Le coût complet de chaque option de production et sa sensibilité au coût du capital et au carburant |
| `analysis/solar.py` | Le productible par site et le classement ressource / évacuation / absorption |
| `analysis/reliability.py` | La mesure du délestage et son coût économique face au coût de l'éviter |
| `analysis/reforms.py` | Les conditions structurelles acquises, défaites ou manquantes, et leur ordre de traitement |
| `analysis/corpus.py` | Le corpus externe, sa couverture, et la confrontation de chaque grandeur interne aux valeurs publiées |
| `analysis/decisions.py` | La synthèse : options classées en « sans regret », « conditionnel » et « à préparer » |

## Utilisation

Aucune dépendance externe : bibliothèque standard Python 3.10+ uniquement.

```bash
python -m malinergy valider              # cohérence des jeux de données et des sources
python -m malinergy corpus               # observations externes collectées
python -m malinergy reconcilier          # confronter les calculs aux sources publiées
python -m malinergy comparer             # le Mali face à ses comparateurs
python -m malinergy tarifs               # vérité des couts et incidence de la subvention
python -m malinergy facture 150          # facture mensuelle d'un abonné domestique
python -m malinergy offre                # ordre de mérite et équilibre de puissance
python -m malinergy lcoe --site segou    # coût complet des options de production
python -m malinergy solaire              # classement des sites
python -m malinergy delestage            # historique et coût économique
python -m malinergy reformes             # séquence et chaînons manquants
python -m malinergy decisions            # options d'action classées
python -m malinergy rapport --sortie docs/rapport.md
python -m malinergy export               # JSON consommé par le site
python -m malinergy pdf                  # rapport imprimable dans public/assets/
```

Le rapport complet est versionné dans [`docs/rapport.md`](docs/rapport.md), et sa version
imprimable dans [`public/assets/malinergy-rapport.pdf`](public/assets/malinergy-rapport.pdf).
Le rendu PDF demande une dépendance optionnelle : `pip install 'malinergy[pdf]'`.

### Tests

```bash
python -m unittest discover -s tests -t .
```

Les tests vérifient deux choses distinctes : que les formules sont justes (invariants
vérifiables à la main, comme le facteur d'annuité ou la tarification par palier) et que
les conclusions qualitatives du rapport découlent bien des données — par exemple que le
meilleur site solaire du pays n'est pas celui dont la ressource est la meilleure.

## Le corpus externe et la réconciliation

Le Mali est rarement le sujet d'un jeu de données : il est presque toujours une ligne parmi
deux cents pays. La plateforme collecte ces observations — indicateurs de la Banque
mondiale, rapports du FMI, suivi ODD 7, registres de centrales, enquêtes entreprises,
comparaisons régionales — dans `malinergy/data/observations.json`, puis **confronte chacune
à la grandeur correspondante qu'elle calcule elle-même**.

C'est le mécanisme le plus utile du dépôt. Il a déjà produit une correction de fond (la
subvention budgétaire et la ponction budgétaire totale sont deux grandeurs distinctes, que
les sources confondaient), deux confirmations indépendantes du modèle tarifaire, et une
divergence qui reste affichée faute d'être tranchée. Une divergence signalée est une
question ouverte ; une divergence lissée est une erreur cachée.

La campagne de collecte, ses limites et ce qui manque encore sont documentés dans
[`docs/corpus.md`](docs/corpus.md).

## Le site

Interface React + Vite. Elle n'inscrit aucun chiffre en dur : elle lit les fichiers
produits par `python -m malinergy export` dans `public/data/`.

```bash
npm install
npm run data     # régénère public/data à partir de malinergy/data
npm run dev
npm run build    # exécute l'export puis construit le site
```

## Structure

```
malinergy/
  data/            jeux de données sourcés (tarifs, parc, réseau, solaire, délestage, réformes)
  analysis/        calculs décisionnels
  datasets.py      chargement, validation, provenance
  report.py        rapport de décision en Markdown
  export.py        export JSON pour le site
  cli.py           interface en ligne de commande
docs/
  methodologie.md  comment chaque chiffre est obtenu, et ce qu'il ne permet pas de conclure
  sources.md       lecture du registre des sources, et les lacunes prioritaires
  corpus.md        la campagne de collecte externe, ses limites, ce qui manque
  rapport.md       rapport généré
src/               interface React
public/data/       JSON généré (ne pas éditer à la main)
public/assets/     rapport PDF et ressources graphiques
tests/
```

## Contribuer

La priorité est la donnée primaire, pas le raffinement de méthode. Les cinq lacunes qui
limitent aujourd'hui la précision des conclusions sont listées dans
[`docs/sources.md`](docs/sources.md) — états financiers d'EDM-SA, rapports de dispatching,
grilles tarifaires homologuées après 2019, prix des PPA solaires, comptes de
l'électrification rurale.

Pour ajouter une donnée : la placer dans le fichier `malinergy/data` adéquat avec un champ
`source` pointant vers une entrée de `sources.json`, puis lancer
`python -m malinergy valider`.

**Convention d'écriture** : les identifiants, statuts et clés des jeux de données restent
en ASCII — ils servent d'appariement entre fichiers et avec le code. Les champs destinés à
l'affichage (`label`, `name`, `note`, `summary`, `title`, `impact`, `why_it_matters`,
`caveat`) sont en français accentué.

## Licence

Données et textes sous CC-BY 4.0. Citer : « Malinergy, <date de consultation> ».

---
© 2026 Malinergy
