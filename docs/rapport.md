# Malinergy — rapport de décision sur le secteur électrique malien

Instantané des données : 2026-01. Toutes les valeurs monétaires sont en francs CFA (XOF).

## Ce que les données imposent

1. Chaque kWh vendu rapporte 96 FCFA et en coûte 147. L'écart de 52 FCFA/kWh n'est pas un choix tarifaire: c'est une dette de 75 milliards FCFA par an qui se reporte sur le budget, puis sur les fournisseurs.

2. Le délestage a coûté environ 135 milliards FCFA à l'économie sur douze mois, pour 145 GWh non fournis (10.0% des ventes). Subir un kWh manquant coûte 3.9 fois plus cher que le produire au coût marginal: l'inaction est l'option la plus chère du tableau.

3. Le déficit est un déficit de puissance ferme, pas d'énergie: 489 MW disponibles le soir contre 620 MW de pointe et 800 MW de demande latente. Ajouter du solaire sans stockage réduit la facture de carburant sans réduire le délestage du soir.

4. L'irradiation ne varie que de 11% entre le meilleur et le moins bon site du pays, alors que le coût de raccordement varie d'un facteur 125. Choisir un site pour son ensoleillement plutôt que pour son raccordement, c'est optimiser la variable la moins importante.

5. Les mesures sans regret identifiées valent 18 milliards FCFA par an et ne dépendent d'aucune réforme non acquise. Elles portent sur l'énergie déjà produite: pertes, recouvrement, arriérés.

## Tarifs, coûts et subventions

- Recette moyenne hors taxes : **96 FCFA/kWh**
- Coût moyen de fourniture : **147 FCFA/kWh**
- Écart couvert par le budget : **52 FCFA/kWh**, soit 75.0 Md FCFA par an
- Taux de couverture des coûts : **65%**

### Facture d'un abonné domestique

La grille est progressive par palier: le prix moyen payé dépend fortement du niveau de consommation, ce qui rend trompeuse toute comparaison fondée sur un tarif unique.

| kWh/mois | Facture (FCFA) | Prix moyen (FCFA/kWh) |
|---|---|---|
| 25 | 2 950 | 118 |
| 50 | 4 720 | 94 |
| 75 | 7 139 | 95 |
| 100 | 9 558 | 96 |
| 150 | 16 048 | 107 |
| 200 | 22 538 | 113 |
| 300 | 38 232 | 127 |
| 500 | 69 620 | 139 |
| 1000 | 148 090 | 148 |

### Qui capté la subvention

| Catégorie | Part des ventes | Part des abonnés | Recette (FCFA/kWh) | Écart au coût | Part de la subvention |
|---|---|---|---|---|---|
| Basse tension — usage domestique général | 38% | 55% | 92 | 55 | 40% |
| Moyenne tension — industrie et gros tertiaire | 40% | 1% | 96 | 51 | 40% |
| Basse tension — tranche sociale | 7% | 34% | 60 | 87 | 12% |
| Basse tension — professionnel / petite entreprise | 11% | 8% | 122 | 25 | 5% |
| Éclairage public — basse tension | 2% | 1% | 108 | 39 | 2% |
| Éclairage public — moyenne tension | 2% | 1% | 113 | 34 | 1% |

La tranche sociale représente 34% des abonnés et capté 12% de la subvention. Une aide adossée au kWh se répartit comme la consommation, donc à l'inverse du besoin social.

## Offre: ordre de mérite et équilibre de puissance

L'empilement ci-dessous est calculé à la pointe du soir, solaire absent. C'est l'État de réseau qui dimensionne le système et qui fixe la valeur économique d'un kWh économisé.

| Moyen | Filière | Disponible (MW) | Cumul (MW) | Coût variable (FCFA/kWh) |
|---|---|---|---|---|
| Sélingué | hydro | 31 | 31 | 14 |
| Sotuba | hydro | 3 | 34 | 14 |
| Gouina | hydro | 38 | 72 | 16 |
| Félou | hydro | 22 | 94 | 16 |
| Manantali | hydro | 78 | 172 | 18 |
| Solaire PV sous contrat (IPP) | solar_pv | 0 | 172 | 55 |
| Import Côte d'Ivoire (interconnexion 225 kV) | import | 105 | 277 | 88 |
| Centrales HFO EDM (Balingue, Darsalam, Sirakoro) | thermal_hfo | 118 | 395 | 172 |
| Groupes loués (diesel/HFO) | thermal_rental | 94 | 489 | 235 |

- Pointe appelée : **620 MW**
- Puissance ferme disponible le soir : **489 MW** (marge : -131 MW)
- Demande latente, délestage compris : **800 MW** (déficit ferme : 311 MW)
- Coût moyen de production : **108 FCFA/kWh**, soit 193.0 Md FCFA par an

Le déficit est un déficit de **puissance ferme**, pas d'énergie. Toute solution qui n'ajoute pas de capacité disponible après le coucher du soleil laisse le délestage du soir inchangé, quel que soit le volume d'énergie qu'elle produit.

## Délestage: mesure et coût économique

| Année | Heures/jour (moy.) | Énergie non fournie (GWh) | Pire mois | Heures/jour |
|---|---|---|---|---|
| 2023 | 2.5 | 49 | 2023-05 | 4.6 |
| 2024 | 4.0 | 123 | 2024-05 | 7.3 |
| 2025 | 4.6 | 162 | 2025-05 | 8.4 |
| 2026 | 5.6 | 114 | 2026-05 | 7.8 |

- Sur douze mois glissants : **145 GWh** non fournis, soit 10.0% des ventes
- Coût pour l'économie : **134.9 Md FCFA** par an (112.0 Md FCFA pour les entreprises)
- Coût moyen d'un kWh non fourni : **928 FCFA**, soit **3.9 fois** le coût marginal de production
- Autoproduction de secours : **333 FCFA/kWh**, soit environ 21.8 Md FCFA de carburant privé par an

Fenêtre critique : avril, mai, juin. L'étiage des fleuves — donc la baisse de l'hydroélectricité — coïncide avec la pointe de climatisation. Les deux contraintes tombent au même moment: c'est cette fenêtre, et non la moyenne annuelle, que toute solution doit viser.

## Ressource solaire et choix des sites

| Site | GHI (kWh/m2/j) | Productible (kWh/kWc/an) | Facteur de charge | Distance réseau (km) | Score | Orientation |
|---|---|---|---|---|---|---|
| Bamako | 5.75 | 1 719 | 19.6% | 0 | 0.88 | priorité réseau interconnecté |
| Kayes | 5.95 | 1 779 | 20.3% | 8 | 0.73 | priorité réseau interconnecté |
| Ségou | 5.90 | 1 764 | 20.1% | 15 | 0.73 | priorité réseau interconnecté |
| Mopti | 6.05 | 1 716 | 19.6% | 40 | 0.60 | conditionné au renforcement de l'antenne |
| Koutiala | 5.60 | 1 674 | 19.1% | 20 | 0.56 | priorité réseau interconnecté |
| Sikasso | 5.45 | 1 629 | 18.6% | 10 | 0.53 | second rang |
| Nioro du Sahel | 6.00 | 1 702 | 19.4% | 120 | 0.51 | conditionné au renforcement de l'antenne |
| Kidal | 6.35 | 1 801 | 20.6% | isole | 0.29 | hybride PV-diesel-stockage en système isolé |
| Tombouctou | 6.25 | 1 773 | 20.2% | isole | 0.27 | hybride PV-diesel-stockage en système isolé |
| Gao | 6.20 | 1 758 | 20.1% | isole | 0.26 | hybride PV-diesel-stockage en système isolé |

L'écart de productible entre le meilleur et le moins bon site est de **11%**. L'écart de coût de raccordement est d'un facteur **125**. La ressource n'est donc pas le critère de sélection: le raccordement et la charge locale le sont.

Corollaire opérationnel: les sites du nord, où l'irradiation est la meilleure, ne relèvent pas du réseau interconnecté mais de l'hybridation des systèmes isolés, où leur concurrent n'est pas le tarif mais un diesel à plus de 280 FCFA/kWh.

## Coût complet des options de production

| Technologie | Facteur de charge | Capital | Exploitation | Combustible | LCOE (FCFA/kWh) | Délai (mois) |
|---|---|---|---|---|---|---|
| PV au sol raccordé réseau | 20% | 35 | 6 | 0 | **41** | 18 |
| Hydro Kénié (42 MW) | 45% | 55 | 8 | 0 | **63** | 60 |
| PV + stockage 4 h | 19% | 74 | 11 | 0 | **86** | 24 |
| Groupe HFO neuf | 55% | 15 | 5 | 172 | **193** | 30 |
| Location de groupes (contrat 3 ans) | 40% | 0 | 33 | 235 | **268** | 4 |

Référence de comparaison: le coût marginal du parc à la pointe est de **235 FCFA/kWh**. Toute option dont le LCOE est inférieur à ce niveau dégage un gain net des sa mise en service.

Sensibilité du solaire raccordé: le facteur dominant est **coût du capital** (amplitude 24 FCFA/kWh pour le capital contre 0 pour le carburant). Autrement dit, le prix du kWh solaire malien des vingt prochaines années se décide dans la solvabilité de l'acheteur, pas dans le choix du site ni dans la technologie des modules.

## Séquence des réformes: acquis, défaits, manquants

15 décisions recensées entre 1960 et 2025. **20%** ont été annulées ou ont régressé — Privatisation partielle d'EDM (SAUR/IPS) (2000), Retrait de SAUR (2005), Arriérés envers la SOGEM et les fournisseurs régionaux (2025).

### Conditions structurelles non acquises

| Condition | Statut | Levier | Pourquoi elle compte |
|---|---|---|---|
| Régulateur doté de l'autonomie de décision tarifaire | partiel | 5 | Sans homologation effective, aucun signal-prix ne circule et l'écart coût-tarif se transforme en dette. |
| Trajectoire pluriannuelle de convergence tarif-coût | manquant | 4 | C'est la variable qui détermine si les économies de carburant profitent au budget ou disparaissent dans les arriérés. |
| Comptage, facturation et recouvrement fiabilisés | en_cours | 3 | Chaque point de pertes non techniques récupère vaut plusieurs milliards FCFA par an, sans nouvelle capacité. |
| Solvabilité de l'acheteur unique (garantie de paiement) | manquant | 2 | Détermine le WACC des IPP, donc le prix du kWh solaire pendant vingt ans. |
| Subvention ciblée sur les ménages pauvres plutôt que sur le kWh | manquant | 0 | Une subvention au kWh bénéficie surtout aux gros consommateurs raccordés; le ciblage libère des marges budgétaires à impact social égal. |
| Appels d'offres compétitifs standardisés pour les IPP | partiel | 0 | Le prix du PPA solaire dépend davantage de la qualité de la procédure et de la bancabilité que de la ressource. |
| Plan directeur de moindre coût révisé et publié | partiel | 0 | En son absence, les décisions d'urgence (location de groupes) se substituent à la planification. |
| Cadre tarifaire et de sortie pour les mini-réseaux | partiel | 0 | Conditionne l'électrification rurale privée et le sort des actifs lorsque le réseau principal arrive. |

### Ordre de traitement

Les dépendances imposent un ordre: une condition ne produit son effet qu'après celles dont elle dépend.

1. Régulateur doté de l'autonomie de décision tarifaire
2. Trajectoire pluriannuelle de convergence tarif-coût
3. Comptage, facturation et recouvrement fiabilisés
4. Solvabilité de l'acheteur unique (garantie de paiement)
5. Subvention ciblée sur les ménages pauvres plutôt que sur le kWh
6. Plan directeur de moindre coût révisé et publié
7. Cadre tarifaire et de sortie pour les mini-réseaux
8. Appels d'offres compétitifs standardisés pour les IPP

> 20% des décisions recensées ont été annulées ou ont régressé. Une réforme qui ne survit pas à un cycle politique ne produit aucun rendement: la séquence doit privilégier les mesures dont l'effet est visible avant l'échéance suivante.

> Aucune mesure de la catégorie financière n'est arrivée à son terme. L'infrastructure a avancé, l'équilibre financier non — c'est pourquoi une capacité nouvelle se traduit par une dette nouvelle plutôt que par un service amélioré.

> Indice de complétude des conditions structurelles: 28%. En dessous de la moitié, le rendement des investissements physiques reste capté par le déficit d'exploitation.

## Que faire, dans quel ordre

### Sans regret

Rentables, réalisables, sans prérequis de réforme non acquis.

| Option | Gain annuel (ajusté du risque) | Investissement | Retour | Délai | Risque | Condition bloquante |
|---|---|---|---|---|---|---|
| Hybridation PV + stockage des centres isolés du nord | 9.1 Md FCFA | 46.0 Md FCFA | 3.0 ans | 20 mois | élevé | — |
| Porter le taux de recouvrement de 86 % à 94 % | 8.9 Md FCFA | 12.0 Md FCFA | 1.1 ans | 18 mois | moyen | — |

- **Hybridation PV + stockage des centres isolés du nord** — Les centres isolés produisent à 280 FCFA/kWh avec du gasoil acheminé par route. Hybrider 55% de cette énergie à environ 105 FCFA/kWh supprime aussi la vulnérabilité logistique.
- **Porter le taux de recouvrement de 86 % à 94 %** — Passer de 86% à 94% de recouvrement sur des ventes déjà réalisées: aucune capacité nouvelle, aucun kWh supplémentaire à produire.

### Conditionnel

Le gain est réel mais suppose une condition structurelle aujourd'hui absente.

| Option | Gain annuel (ajusté du risque) | Investissement | Retour | Délai | Risque | Condition bloquante |
|---|---|---|---|---|---|---|
| 100 MW de PV avec stockage 4 h pour la pointe du soir | 63.4 Md FCFA | 98.0 Md FCFA | 1.2 ans | 24 mois | moyen | Solvabilité de l'acheteur unique (garantie de paiement) |
| 200 MW de PV raccordé sur les sites les mieux placés | 60.3 Md FCFA | 104.0 Md FCFA | 1.6 ans | 18 mois | faible | Solvabilité de l'acheteur unique (garantie de paiement) |
| Porter la capacité d'import à 250 MW (renforcement 225 kV) | 56.7 Md FCFA | 88.0 Md FCFA | 1.2 ans | 42 mois | moyen | Solvabilité de l'acheteur unique (garantie de paiement) |
| Remplacer la subvention au kWh par une subvention ciblée | 30.4 Md FCFA | 4.0 Md FCFA | 0.1 ans | 12 mois | élevé | Trajectoire pluriannuelle de convergence tarif-coût, Subvention ciblée sur les ménages pauvres plutôt que sur le kWh |
| Sortir des groupes loués au profit de capacité propre et d'import | 13.3 Md FCFA | 62.0 Md FCFA | 2.8 ans | 30 mois | élevé | Solvabilité de l'acheteur unique (garantie de paiement) |
| Apurer les arriérés envers la SOGEM et les fournisseurs régionaux | 10.5 Md FCFA | 54.0 Md FCFA | 4.9 ans | 12 mois | faible | Solvabilité de l'acheteur unique (garantie de paiement) |

- **100 MW de PV avec stockage 4 h pour la pointe du soir** — 100 MW / 4 h restituent l'énergie à l'heure où le parc appelle son kWh à 235 FCFA et où le délestage coûte 928 FCFA/kWh à l'économie. C'est la seule option non thermique qui agisse sur la pointe du soir.
- **200 MW de PV raccordé sur les sites les mieux placés** — 200 MW produisant 353 GWh/an déplacent un kWh à 235 FCFA pour un PPA à 55 FCFA. Le gain est du carburant, pas de la capacité: la pointe du soir reste inchangée.
- **Porter la capacité d'import à 250 MW (renforcement 225 kV)** — 100 MW de transit supplémentaire à 88 FCFA/kWh contre 235 FCFA/kWh en local. Le gain suppose un excédent exportable côté ivoirien et le paiement régulier des factures.
- **Remplacer la subvention au kWh par une subvention ciblée** — Aujourd'hui 52% de la subvention va aux ménages, mais seulement 12% à la tranche sociale, qui représente 34% des abonnés. Cibler le soutien sur les ménages les plus modestes libère l'essentiel de l'enveloppe à impact social équivalent.
- **Sortir des groupes loués au profit de capacité propre et d'import** — Le loyer de capacité (8 Md FCFA/an sur la part remplacée) est payé en devises et disparaît intégralement. Le kWh loué passe de 235 à 172 FCFA.
- **Apurer les arriérés envers la SOGEM et les fournisseurs régionaux** — Rétablir l'accès normal à l'hydro partagé substitue environ 50 GWh à 16 FCFA/kWh à du thermique à 235 FCFA/kWh. La dépense est un apurement de trésorerie, pas un investissement.

### À préparer

Le délai ou le retour sur investissement dépasse le cycle de la crise courante.

| Option | Gain annuel (ajusté du risque) | Investissement | Retour | Délai | Risque | Condition bloquante |
|---|---|---|---|---|---|---|
| Passer l'antenne Ségou-Mopti en 150 kV | 17.5 Md FCFA | 71.0 Md FCFA | 3.2 ans | 42 mois | moyen | — |
| Ramener les pertes réseau de 18,5 % à 15,5 % | 13.6 Md FCFA | 78.0 Md FCFA | 4.6 ans | 24 mois | moyen | — |

- **Passer l'antenne Ségou-Mopti en 150 kV** — L'antenne 33 kV plafonne à 18 MW: le centre du pays est délesté faute de transit et n'a aucune marge pour accueillir du solaire. Le passage en 150 kV dégage 72 MW et rend raccordables environ 36 MW de PV local.
- **Ramener les pertes réseau de 18,5 % à 15,5 %** — 3 points de pertes récupérés représentent 53 GWh: du carburant non brûlé au coût marginal (235 FCFA/kWh) et de l'énergie désormais facturée.

### Séquence

**0-18 mois — récupérer ce qui existe déjà**

Aucune de ces mesures ne demande de capacité nouvelle. Elles portent sur l'énergie déjà produite et déjà vendue, et leur rendement est immédiat.

Gain annuel cumulé : 8.9 Md FCFA — investissement : 12.0 Md FCFA.

**18-36 mois — substituer le carburant importé**

Le solaire raccordé et la sortie des groupes loués attaquent le poste de coût dominant. Leur rendement suppose un acheteur solvable: c'est la condition à lever en parallèle, pas après.

Gain annuel cumulé : 200.6 Md FCFA — investissement : 446.0 Md FCFA.

**36 mois et au-delà — lever les contraintes physiques**

Réseau de transport et interconnexion: ces ouvrages ne résolvent pas la crise courante mais déterminent si la décennie suivante se joue sur du solaire bon marché ou sur du diesel.

Gain annuel cumulé : 74.2 Md FCFA — investissement : 159.0 Md FCFA.

## Provenance et limites

108 références de source dans les jeux de données : 54 de confiance haute, 22 moyenne, 32 faible.

| Identifiant | Éditeur | Année | Confiance | Nature |
|---|---|---|---|---|
| gpp-mali-prix | GlobalPetrolPrices | 2025 | faible | compilation |
| malinergy-estimation | Malinergy | 2026 | faible | estimation |
| akdn-edm-ppp | Aga Khan Development Network | 2010 | haute | institutionnel |
| wb-amader-concessions | Banque mondiale | 2017 | haute | rapport |
| afdb-desert-to-power-mali | Banque africaine de développement | 2020 | haute | rapport |
| wb-mali-esrap | Banque mondiale | 2021 | haute | rapport |
| cif-mali-rei | Climate Investment Funds | 2023 | haute | rapport |
| gsa-mali | Banque mondiale / Solargis | 2024 | haute | données |
| cree-grille-bt | Commission de Régulation de l'Électricité et de l'Eau (CREE) | 2019 | moyenne | réglementaire |
| cree-eclairage-public | CREE / EDM-SA | 2020 | moyenne | réglementaire |
| omvs-sogem | OMVS / SOGEM | 2022 | moyenne | institutionnel |
| energypedia-mali | energypedia | 2024 | moyenne | compilation |
| apa-dette-omvs | APA News | 2025 | moyenne | presse |

Les valeurs marquées `malinergy-estimation` sont des hypothèses de travail explicites, jamais des relevés officiels. Elles sont concentrées sur les agrégats d'exploitation d'EDM-SA, qui ne sont pas publiés de façon régulière, et sur la série de délestage, qui est une reconstruction. Chaque conclusion de ce rapport reste valable tant que l'ordre de grandeur de ces hypothèses tient; remplacer une valeur dans `malinergy/data` suffit à recalculer l'ensemble.
