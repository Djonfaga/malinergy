# Sources

Le registre complet vit dans `malinergy/data/sources.json` ; ce document en donne la
lecture, avec ce que chaque source apporte et ce qu'elle ne couvre pas.

Pour l'afficher a jour :

```bash
python -m malinergy sources
```

## Sources de confiance haute

| Source | Apport | Limite |
|---|---|---|
| Banque mondiale — *Mali Electricity System Reinforcement and Access Expansion Project* (2021) | Deficit structurel, subvention de 100-150 MUSD/an, croissance de la demande, taux d'acces, pertes reseau | Anterieure a la crise de 2024-2025 |
| BAD — *Desert to Power, feuille de route Mali* (2020) | Ressource solaire, pipeline PV, sequencage | Objectifs programmatiques, non realises |
| Climate Investment Funds — *Mali REI Investment Plan* (2023) | Contraintes d'integration du PV variable, besoins de stockage, cout du capital IPP | Perimetre EnR seulement |
| Banque mondiale / Solargis — *Global Solar Atlas* (2024) | GHI par localite | Incertitude ~4 % sur la ressource |
| Banque mondiale — *Rural Electrification Concessions in Mali* (2017) | Modele AMADER, couts des mini-reseaux, centres isoles | Millesime ancien |
| AKDN — *PPP EDM / IPS (WA)* | Chronologie de la privatisation de 2000 et du retrait de SAUR | Point de vue d'une partie prenante |

## Sources de confiance moyenne

| Source | Apport | Limite |
|---|---|---|
| CREE — grille tarifaire basse tension (2019) | Tranches et niveaux de la grille BT | Millesime a reverifier a chaque homologation |
| CREE / EDM-SA — eclairage public (2020) | Tarification aux collectivites | Perimetre etroit |
| OMVS / SOGEM | Puissances installees de Manantali, Felou, Gouina et cle de repartition | La part malienne varie selon les annees |
| APA News (2025) | Arrieres d'environ 54 Md FCFA envers la SOGEM | Source de presse, non confirmee par un etat financier |
| energypedia — *Mali Energy Situation* | Historique institutionnel | Compilation secondaire |

## Sources de confiance faible

| Source | Apport | Limite |
|---|---|---|
| GlobalPetrolPrices | Ordre de grandeur du prix moyen | Agregat sans methodologie publiee |
| `malinergy-estimation` | Agregats d'exploitation EDM-SA, prix des carburants, cout du kWh non fourni, serie de delestage | Hypotheses de travail explicites, jamais des releves officiels |

## Ce qui manque

Les lacunes suivantes limitent aujourd'hui la precision de la plateforme. Elles sont
listees ici parce qu'obtenir l'une d'elles ferait davantage progresser la qualite des
conclusions que n'importe quel raffinement de methode :

1. **Les etats financiers annuels d'EDM-SA** — ventes par categorie, recettes, structure
   de couts, arrieres. Ils remplaceraient a eux seuls la majorite des estimations.
2. **Les rapports de dispatching** — energie non distribuee, disponibilite par centrale,
   volumes importes reels. Ils transformeraient la serie de delestage reconstruite en
   serie observee.
3. **Les grilles tarifaires homologuees postérieures a 2019**, avec les deliberations de
   la CREE.
4. **Les prix des PPA solaires signes**, meme agreges. Le prix du kWh solaire est la
   variable dont depend l'essentiel du benefice calcule ici.
5. **Les comptes de l'electrification rurale** — nombre de clients, tarifs et couts des
   concessions AMADER.

Toute contribution portant sur l'un de ces cinq points est prioritaire sur toute autre.
