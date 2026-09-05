# Methodologie

Ce document explique comment les chiffres du depot sont obtenus, ce qu'ils valent, et
ce qu'ils ne permettent pas de conclure. Il est destine a etre lu avant toute citation
d'un resultat de la plateforme.

## Principe de base

**Aucune valeur chiffree ne vit dans le code.** Tout nombre est stocke dans
`malinergy/data/*.json` et porte un identifiant de source declare dans
`malinergy/data/sources.json`. Le chargement echoue si une reference manque
(`Registry.validate`). La consequence pratique: corriger une donnee suffit a
recalculer l'ensemble des conclusions, sans toucher a une seule ligne de calcul.

Trois niveaux de confiance sont utilises :

| Niveau | Signification |
|---|---|
| `haute` | Publication institutionnelle ou rapport d'un bailleur, verifiable en ligne. |
| `moyenne` | Source secondaire fiable, ou donnee primaire dont le millesime est ancien. |
| `faible` | Hypothese de travail Malinergy, explicitement identifiee comme telle. |

Les valeurs marquees `malinergy-estimation` ne sont jamais presentees comme des
releves officiels. Elles se concentrent sur deux zones ou la donnee primaire n'est pas
publiee de facon reguliere : les agregats d'exploitation d'EDM-SA et la serie de
delestage.

## Tarifs et verite des couts

La grille basse tension est **progressive par palier** : chaque kWh est facture au prix
de sa tranche, et non au prix de la tranche atteinte. `tariff.energy_charge` implemente
ce calcul, ce qui rend visible un point souvent perdu dans le debat public : le prix
moyen paye par un menage varie de 94 a 148 FCFA/kWh selon sa consommation, pour une
seule et meme grille.

Le cout moyen de fourniture n'est pas releve : il est **reconstruit par le bas**.

```
cout moyen = recette moyenne HT + subvention publique / kWh vendus
```

Ce choix limite volontairement les entrees exogenes a deux grandeurs verifiables : la
grille homologuee et le montant de la subvention budgetaire. Il evite d'avoir a
postuler une structure de couts d'EDM-SA que rien de public ne permet d'etayer.

L'**incidence de la subvention** repartit ensuite l'ecart cout-tarif au prorata de la
consommation de chaque categorie. C'est la propriete mecanique d'une aide adossee au
kWh : elle suit la consommation, donc a l'inverse du besoin social.

## Ordre de merite et cout marginal

`dispatch.merit_order` empile le parc par cout variable croissant en appliquant a chaque
moyen sa disponibilite. Deux etats de reseau sont distingues :

- **journee, solaire disponible** — pertinent pour la consommation de carburant ;
- **pointe du soir, solaire absent** — pertinent pour le dimensionnement et pour la
  valeur d'un kWh economise.

Le cout marginal par defaut est celui de la pointe du soir. C'est l'hypothese
structurante de toute l'analyse : elle explique pourquoi le solaire sans stockage
reduit la facture de combustible sans reduire le delestage ressenti.

## Delestage

<a id="delestage"></a>

La serie mensuelle de `outages.json` est une **reconstruction**, pas un releve
d'exploitation. Elle combine trois determinants documentes :

1. la saisonnalite hydrologique — l'etiage des fleuves de mars a juin reduit
   l'hydroelectricite, la ressource la moins chere du parc ;
2. la pointe de climatisation, qui culmine sur la meme fenetre ;
3. l'aggravation du deficit constatee sur 2023-2025.

L'energie non distribuee en decoule : `heures x puissance delestee moyenne x jours`.
Le resultat — de l'ordre de 10 % des ventes — est coherent avec le deficit de puissance
ferme calcule independamment par `dispatch.capacity_balance`, ce qui constitue le seul
controle croise disponible. **Cette serie ne doit pas etre citee comme une statistique
officielle.**

Le cout economique valorise chaque kWh non fourni au cout que son absence impose a
l'usager, et non au tarif : autoproduction de secours pour les menages, perte
d'activite pour les entreprises. Les valeurs retenues sont des bornes basses.

## LCOE

Formule standard, annuite constante :

```
LCOE = (capex x CRF + opex fixe) / (facteur de charge x 8760) + cout du combustible
CRF  = i (1+i)^n / ((1+i)^n - 1)
```

Le taux d'actualisation depend du porteur : public, IPP, ou menage. C'est une variable
de decision, pas un parametre technique — la difference entre 8 % et 14 % pese davantage
sur le prix du kWh solaire malien que le choix du site ou la technologie des modules.
`lcoe.sensitivity` chiffre cet arbitrage.

Le facteur de charge du solaire n'est pas saisi : il est derive de l'irradiation du site
retenu.

## Solaire

```
productible (kWh/kWc/an) = GHI x gain d'inclinaison x 365 x ratio de performance
```

Le ratio de performance integre temperature, salissure, cablage et onduleur ; une perte
supplementaire est appliquee aux sites sahéliens exposes a l'harmattan.

Le classement des sites pondere trois criteres : ressource (0,25), cout d'evacuation
(0,40) et charge locale absorbable (0,35). Cette ponderation traduit un fait mesurable
et non une preference : l'ecart de productible entre le meilleur et le moins bon site du
pays est d'environ 11 %, quand l'ecart de cout de raccordement atteint un facteur 125.

## Reformes

Les conditions structurelles sont reliees par un graphe de dependances : une condition
« debloque » celles dont le rendement en depend. `reforms.critical_path` en tire un tri
topologique, c'est-a-dire l'ordre dans lequel les lacunes doivent etre traitees pour que
chacune produise son effet.

## Options d'action

`interventions.json` ne stocke **que** les parametres de dimensionnement, de cout et de
risque. Le benefice annuel est toujours recalcule a partir des jeux de donnees par le
modele nomme dans `benefit_model` — il n'est jamais saisi a la main, precisement pour
qu'aucune option ne puisse etre favorisee par un chiffre pose d'autorite.

Le classement final n'est pas un score unique. Les options sont reparties en trois
categories, parce qu'elles n'appellent pas les memes decideurs :

- **sans regret** — retour en moins de quatre ans, delai inferieur a trente mois, aucune
  condition structurelle bloquante ;
- **conditionnel** — le gain est reel mais suppose une reforme aujourd'hui absente ;
- **a preparer** — le delai depasse le cycle de la crise en cours.

Le benefice est ajuste du risque par un coefficient explicite (0,95 / 0,80 / 0,60) qui
represente la probabilite de realisation hors dependances de reforme.

## Ce que la plateforme ne fait pas

- Elle ne simule pas le reseau au pas horaire : les contraintes de transit sont traitees
  en ordres de grandeur, pas en ecoulement de charge.
- Elle ne modelise pas l'hydrologie : la saisonnalite est parametree, non simulee.
- Elle ne prevoit pas la demande : la croissance est une entree, pas un resultat.
- Elle n'arbitre pas le cout politique d'une reforme tarifaire. Elle en chiffre le
  rendement budgetaire et signale ou l'arbitrage se situe.
