# Corpus externe : ce qui a été cherché, trouvé, et ce qui manque

Ce document rend compte de la campagne de collecte : le périmètre visé, la méthode,
ce qui a été effectivement récupéré, et les limites qu'il faut connaître avant de citer
un chiffre de la plateforme.

## Ce que « toutes les données du monde » veut dire en pratique

Le Mali est rarement le sujet d'un jeu de données. Il est presque toujours **une ligne
parmi deux cents pays** : un indicateur de la Banque mondiale, une ligne du suivi ODD 7,
une entrée d'un registre régional de centrales, un profil dans les statistiques IRENA.
La collecte a donc visé deux familles :

1. les sources **sur** le Mali — CREE, EDM-SA, AMADER, OMVS, feuilles de route sectorielles ;
2. les sources **où le Mali figure** sans en être le sujet — indicateurs mondiaux, enquêtes
   entreprises, registres de centrales, comparaisons régionales, rapports du FMI, suivi
   du Power Pool ouest-africain.

La seconde famille est celle qui apporte les comparateurs, et donc le sens : savoir que le
Mali consomme 90 kWh par habitant ne dit rien tant qu'on ignore que la moyenne africaine
est à 500.

## Limite technique de la collecte

**L'accès réseau direct aux interfaces de données est bloqué dans l'environnement
d'exécution.** Les appels vers `api.worldbank.org`, `ourworldindata.org`,
`api.ember-energy.org`, `data.worldbank.org`, `en.wikipedia.org` et les autres hôtes de
données sont refusés par la politique de sortie réseau (code 403 sur le CONNECT). Le
téléchargement en masse des jeux de données n'a donc **pas** pu être réalisé.

La collecte s'est faite par recherche documentaire : les valeurs consignées dans
`malinergy/data/observations.json` sont celles que les sources publiques ont exposées, avec
leur référence. Chacune porte son éditeur, son année et son niveau de confiance.

Conséquence pratique : le corpus contient les **agrégats et les points saillants**, pas les
séries annuelles complètes. Une série longue — l'accès à l'électricité année par année
depuis 1990, la production mensuelle par filière — demande le téléchargement direct.

## Ce que contient le corpus

Le décompte à jour :

```bash
python -m malinergy corpus
```

Familles couvertes :

| Famille | Ce qu'elle apporte |
|---|---|
| Indicateurs mondiaux (Banque mondiale) | Accès à l'électricité, pertes réseau, consommation par habitant |
| Finances publiques (FMI) | Subvention budgétaire à EDM-SA, prix de vente moyen, cadrage macro |
| Mix et intensité carbone (Ember, Low Carbon Power) | Part bas carbone, gCO2/kWh, production par filière |
| Prix relevés (GlobalPetrolPrices) | Prix ménages et entreprises, comparaison mondiale |
| Intégration régionale (WAPP, OMVS, ESMAP) | Clé de répartition de Manantali, synchronisation régionale |
| Électrification rurale (IRENA, recherche de terrain) | Nombre de mini-réseaux, ménages desservis, tarifs pratiqués |
| Registres de centrales | Centrales solaires en construction, hybrides miniers |
| Engagements climatiques (CDN) | Cibles 2030 d'EnR, d'accès et d'émissions |
| Sécurité d'approvisionnement (presse) | Blocus des convois de carburant depuis septembre 2025 |
| Cuisson (INSTAT, ODD 7) | Dépendance à la biomasse traditionnelle |

## La réconciliation

Chaque observation qui recouvre une grandeur calculée par la plateforme lui est confrontée :

```bash
python -m malinergy reconcilier
```

Le mécanisme a produit trois résultats utiles :

**Une correction de fond.** Deux sources donnaient des chiffres de subvention incompatibles :
40 milliards FCFA par an (FMI) et 100-150 millions USD par an (Banque mondiale). Elles ne
mesurent pas la même chose. La première est la subvention budgétaire votée ; la seconde y
ajoute les arriérés et les emprunts garantis. La plateforme porte désormais les deux, et
l'écart — environ 35 milliards FCFA par an — est nommé pour ce qu'il est : **la part du
déficit du secteur qui ne passe pas par le budget voté**. Le taux de couverture des coûts
passe de 78 % sur la ligne budgétaire à 65 % sur la ponction totale.

**Deux confirmations qui valident le modèle.** Le prix de vente moyen recalculé à partir de
la grille tarifaire et du mix de ventes tombe à 96 FCFA/kWh, contre 97 publié par le FMI —
un écart de 1,4 %, obtenu sans que la valeur du FMI n'entre dans le calcul. La part
malienne de Manantali (104 MW) coïncide exactement avec la clé OMVS documentée.

**Une divergence non résolue, laissée visible.** Un relevé de prix annonce 94,93 FCFA/kWh
« toutes taxes comprises » pour les entreprises, alors que la grille moyenne tension donne
96 FCFA/kWh **hors** taxes. Les deux ne peuvent pas être vraies ensemble. Une délibération
tarifaire de la CREE postérieure à 2019 trancherait. En attendant, la divergence est
affichée : une divergence signalée est une question ouverte, une divergence lissée est une
erreur cachée.

## Ce qui manque encore

Par ordre d'utilité décroissante. Obtenir l'un de ces éléments ferait plus pour la qualité
des conclusions que n'importe quel raffinement de méthode.

1. **Les états financiers annuels d'EDM-SA** — ventes par catégorie, structure de coûts,
   arriérés. Ils remplaceraient la majorité des estimations restantes.
2. **Les rapports de dispatching** — énergie non distribuée réelle, disponibilité par
   centrale, volumes importés. Ils transformeraient la série de délestage reconstruite en
   série observée.
3. **Les microdonnées Enterprise Surveys Mali 2024** — coupures par mois, durée moyenne,
   part du chiffre d'affaires perdue, possession de groupe électrogène. C'est la seule
   mesure directe du coût du délestage pour les entreprises maliennes ; la plateforme
   utilise aujourd'hui une valeur d'usage à sa place.
4. **Les grilles tarifaires homologuées après 2019**, avec les délibérations de la CREE.
5. **Les prix des PPA solaires signés**, même agrégés.
6. **Les séries annuelles complètes** des indicateurs mondiaux, qui demandent un accès
   réseau direct aux interfaces de données.

## Reproduire la collecte

Dans un environnement disposant d'un accès réseau, les jeux suivants sont téléchargeables
directement et couvrent l'essentiel des lacunes 1 à 6 :

| Source | Point d'accès |
|---|---|
| Banque mondiale (indicateurs) | `api.worldbank.org/v2/country/MLI/indicator/<code>?format=json` |
| Our World in Data | `ourworldindata.org/grapher/<slug>.csv?country=~MLI` |
| Ember | `api.ember-energy.org/v1/electricity-generation/yearly?entity_code=MLI` |
| Enterprise Surveys | `microdata.worldbank.org/index.php/catalog/6693` |
| Suivi ODD 7 | `trackingsdg7.esmap.org/country/mali` |
| RISE | `rise.esmap.org/country/mali` |
| IRENA | `irena.org/Publications` (statistiques de capacité, tableaux par pays) |
| Global Solar Atlas | `globalsolaratlas.info` |

Les codes d'indicateurs de la Banque mondiale utiles au secteur : `EG.ELC.ACCS.ZS`
(accès), `EG.ELC.ACCS.RU.ZS` (accès rural), `EG.ELC.ACCS.UR.ZS` (accès urbain),
`EG.ELC.LOSS.ZS` (pertes), `EG.USE.ELEC.KH.PC` (consommation par habitant),
`IC.ELC.OUTG.ZS` (entreprises subissant des coupures), `IC.FRM.OUTG.ZS` (pertes de chiffre
d'affaires dues aux coupures).
