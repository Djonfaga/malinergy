"""Synthese: du corpus de données à un ordre de priorité defendable.

Le principe est de ne jamais comparer des options sur un seul critère. Une décision
énergétique au Mali se juge sur quatre axes que les données du dépôt permettent de
chiffrer separement:

``bénéfice``
    Gain économique annuel recurrent, en FCFA, recalcule à partir des jeux de
    données — jamais saisi à la main.
``délai``
    Mois avant le premier kWh ou le premier franc économisé. Un gain qui arrive
    après la prochaine saison seche ne resout pas la saison seche.
``dépendance``
    Conditions structurelles de réforme sans lesquelles le gain ne se materialise
    pas. C'est ce qui distingue une option sans regret d'une option conditionnelle.
``risque``
    Probabilite que le gain ne soit pas realise, hors dépendances explicites.

Le classement final n'est pas un score unique mais une répartition en trois
catégories d'action, parce que les trois appellent des décideurs differents.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from malinergy.analysis import dispatch, reforms, reliability, solar, tariff
from malinergy.datasets import DataError, Registry

RISK_DISCOUNT = {"faible": 0.95, "moyen": 0.80, "eleve": 0.60}


@dataclass
class Option:
    id: str
    name: str
    lever: str
    annual_benefit_xof: float
    capex_xof: float
    lead_time_months: int
    risk: str
    depends_on: list[str]
    unserved_gwh_addressed: float
    subsidy_relief_xof: float
    rationale: str
    source: str
    blocking_conditions: list[str] = field(default_factory=list)

    @property
    def risk_adjusted_benefit(self) -> float:
        return self.annual_benefit_xof * RISK_DISCOUNT.get(self.risk, 0.7)

    @property
    def payback_years(self) -> float | None:
        if self.annual_benefit_xof <= 0:
            return None
        if self.capex_xof <= 0:
            return 0.0
        return self.capex_xof / self.annual_benefit_xof

    @property
    def benefit_per_xof_invested(self) -> float:
        if self.capex_xof <= 0:
            return float("inf")
        return self.risk_adjusted_benefit / self.capex_xof

    @property
    def category(self) -> str:
        """Sans regret / conditionnel / a preparer.

        Une option est *sans regret* si elle se rembourse en moins de quatre ans et
        ne bute sur aucune condition structurelle absente. Elle est *conditionnelle*
        si son rendement suppose une réforme non acquise. Elle est *a preparer* si
        son délai dépasse le cycle de la crise en cours.
        """
        payback = self.payback_years
        if self.blocking_conditions:
            return "conditionnel"
        if payback is not None and payback <= 4.0 and self.lead_time_months <= 30:
            return "sans regret"
        return "a preparer"


# --------------------------------------------------------------------- modèles


def _loss_reduction(registry: Registry, params: dict) -> tuple[float, float, float, str]:
    value = dispatch.loss_reduction_value(registry, float(params["points"]))
    relief = value["total_value_xof"]
    rationale = (
        f"{params['points']:.0f} points de pertes récupérés représentent "
        f"{value['recovered_kwh'] / 1e6:,.0f} GWh: du carburant non brûlé au coût marginal "
        f"({dispatch.marginal_cost(registry):.0f} FCFA/kWh) et de l'énergie désormais facturée."
    )
    return value["total_value_xof"], 0.0, relief, rationale


def _collection_improvement(
    registry: Registry, params: dict
) -> tuple[float, float, float, str]:
    sales_kwh = registry.value("sector", "aggregates", "sales_gwh_year") * 1e6
    current = registry.value("sector", "aggregates", "collection_rate")
    target = float(params["target_rate"])
    if target <= current:
        raise DataError("la cible de recouvrement doit depasser le taux courant")
    revenue = tariff.average_revenue_per_kwh(registry)
    gain = sales_kwh * (target - current) * revenue
    rationale = (
        f"Passer de {current:.0%} à {target:.0%} de recouvrement sur des ventes déjà "
        f"réalisées: aucune capacité nouvelle, aucun kWh supplémentaire à produire."
    )
    return gain, 0.0, gain, rationale


def _solar_fuel_displacement(
    registry: Registry, params: dict
) -> tuple[float, float, float, str]:
    value = dispatch.displacement_value(registry, float(params["mw"]), site=params["site"])
    gain = value["annual_saving_xof"]
    rationale = (
        f"{params['mw']:.0f} MW produisant {value['annual_kwh'] / 1e6:,.0f} GWh/an déplacent "
        f"un kWh à {value['displaced_cost_xof_per_kwh']:.0f} FCFA pour un PPA à "
        f"{value['ppa_xof_per_kwh']:.0f} FCFA. Le gain est du carburant, pas de la capacité: "
        "la pointe du soir reste inchangée."
    )
    return gain, 0.0, gain, rationale


def _solar_bess_peak(registry: Registry, params: dict) -> tuple[float, float, float, str]:
    mw = float(params["mw"])
    hours = float(params["storage_hours"])
    marginal = dispatch.marginal_cost(registry)  # pointe du soir, solaire absent

    day = dispatch.displacement_value(registry, mw, site=params["site"])
    # L'energie restituee le soir evite le kWh le plus cher du parc et, surtout,
    # de l'energie non distribuee.
    evening_kwh = mw * 1000.0 * hours * 300.0  # 300 jours exploitables par an
    round_trip = 0.88
    ens = reliability.cost_of_unreliability(registry)
    voll = ens["average_voll_xof_per_kwh"]

    # Part de l'energie du soir qui evite reellement du delestage plutot que du
    # carburant: bornee par l'energie non distribuee constatee.
    unserved_kwh = ens["unserved_kwh"]
    avoided_ens_kwh = min(evening_kwh * round_trip, unserved_kwh * 0.5)
    fuel_kwh = evening_kwh * round_trip - avoided_ens_kwh

    lcoe_ppa = 78.0  # PPA solaire+stockage, plus cher que le PV seul
    gain_utility = fuel_kwh * (marginal - lcoe_ppa) + day["annual_saving_xof"] * 0.4
    gain_economy = avoided_ens_kwh * (voll - lcoe_ppa)
    unserved_gwh = avoided_ens_kwh / 1e6

    rationale = (
        f"{mw:.0f} MW / {hours:.0f} h restituent l'énergie à l'heure où le parc appelle "
        f"son kWh à {marginal:.0f} FCFA et où le délestage coûte {voll:.0f} FCFA/kWh à "
        "l'économie. C'est la seule option non thermique qui agisse sur la pointe du soir."
    )
    return gain_utility + gain_economy, unserved_gwh, gain_utility, rationale


def _rental_exit(registry: Registry, params: dict) -> tuple[float, float, float, str]:
    share = float(params["replaced_share"])
    rental = next(p for p in registry["generation"]["plants"] if p["id"] == "location_diesel")
    kwh = (
        float(rental["capacity_mw"])
        * 1000.0
        * float(rental["capacity_factor"])
        * 8760.0
        * share
    )
    fixed = (
        float(rental["fixed_cost_xof_per_kw_month"])
        * float(rental["capacity_mw"])
        * 1000.0
        * 12
        * share
    )
    # L'energie loue est remplacee par l'unite la plus chere du reseau interconnecte
    # hors location: c'est l'hypothese conservatrice, celle qui minimise le gain.
    on_grid = [p for p in dispatch.available_capacity(registry) if p["id"] != "location_diesel"]
    replacement_cost = max(
        float(p.get("ppa_xof_per_kwh") or p["variable_cost_xof_per_kwh"]) for p in on_grid
    )
    gain = kwh * (float(rental["variable_cost_xof_per_kwh"]) - replacement_cost) + fixed
    rationale = (
        f"Le loyer de capacité ({fixed / 1e9:,.0f} Md FCFA/an sur la part remplacée) est payé "
        "en devises et disparaît intégralement. Le kWh loué passe de "
        f"{rental['variable_cost_xof_per_kwh']:.0f} à {replacement_cost:.0f} FCFA."
    )
    return gain, 0.0, gain, rationale


def _isolated_hybrid(registry: Registry, params: dict) -> tuple[float, float, float, str]:
    share = float(params["solar_share"])
    isolated = next(p for p in registry["generation"]["plants"] if p["id"] == "isole_centres")
    kwh = float(isolated["capacity_mw"]) * 1000.0 * float(isolated["capacity_factor"]) * 8760.0
    diesel_cost = float(isolated["variable_cost_xof_per_kwh"])
    hybrid_cost = 105.0  # PV + stockage en site isole, PPA mini-reseau
    gain = kwh * share * (diesel_cost - hybrid_cost)
    rationale = (
        f"Les centres isolés produisent à {diesel_cost:.0f} FCFA/kWh avec du gasoil acheminé "
        f"par route. Hybrider {share:.0%} de cette énergie à environ {hybrid_cost:.0f} FCFA/kWh "
        "supprime aussi la vulnérabilité logistique."
    )
    return gain, 0.0, gain, rationale


def _subsidy_targeting(registry: Registry, params: dict) -> tuple[float, float, float, str]:
    protected = float(params["protected_share"])
    costs = tariff.cost_of_supply(registry)
    incidence = tariff.subsidy_incidence(registry)
    # La subvention conservee couvre les menages protreges; le reste est recupere.
    household_subsidy = sum(
        r["annual_subsidy_xof"] for r in incidence if r["segment"] == "menages"
    )
    other_subsidy = costs["annual_subsidy_xof"] - household_subsidy
    kept = household_subsidy * protected
    relief = costs["annual_subsidy_xof"] - kept - other_subsidy * 0.35
    eff = tariff.targeting_efficiency(registry)
    rationale = (
        f"Aujourd'hui {eff['share_to_households']:.0%} de la subvention va aux ménages, mais "
        f"seulement {eff['share_to_social_tranche']:.0%} à la tranche sociale, qui représente "
        f"{eff['social_customers_share']:.0%} des abonnés. Cibler le soutien sur les ménages "
        "les plus modestes libère l'essentiel de l'enveloppe à impact social équivalent."
    )
    return relief, 0.0, relief, rationale


def _arrears_settlement(registry: Registry, params: dict) -> tuple[float, float, float, str]:
    gain_availability = float(params["availability_gain"])
    hydro = [p for p in registry["generation"]["plants"] if p["type"] == "hydro"]
    marginal = dispatch.marginal_cost(registry)
    extra_kwh = sum(
        float(p["capacity_mw"])
        * 1000.0
        * gain_availability
        * float(p["capacity_factor"])
        * 8760.0
        for p in hydro
    )
    avg_hydro_cost = sum(float(p["variable_cost_xof_per_kwh"]) for p in hydro) / len(hydro)
    gain = extra_kwh * (marginal - avg_hydro_cost)
    rationale = (
        f"Rétablir l'accès normal à l'hydro partagé substitue environ "
        f"{extra_kwh / 1e6:,.0f} GWh à {avg_hydro_cost:.0f} FCFA/kWh à du thermique à "
        f"{marginal:.0f} FCFA/kWh. La dépense est un apurement de trésorerie, pas un investissement."
    )
    return gain, 0.0, gain, rationale


def _import_expansion(registry: Registry, params: dict) -> tuple[float, float, float, str]:
    mw = float(params["additional_mw"])
    imports = next(p for p in registry["generation"]["plants"] if p["id"] == "import_ci")
    kwh = mw * 1000.0 * float(imports["capacity_factor"]) * 8760.0
    marginal = dispatch.marginal_cost(registry)
    gain = kwh * (marginal - float(imports["variable_cost_xof_per_kwh"]))
    rationale = (
        f"{mw:.0f} MW de transit supplémentaire à {imports['variable_cost_xof_per_kwh']:.0f} "
        f"FCFA/kWh contre {marginal:.0f} FCFA/kWh en local. Le gain suppose un excédent "
        "exportable côté ivoirien et le paiement régulier des factures."
    )
    return gain, 0.0, gain, rationale


def _transmission_debottleneck(
    registry: Registry, params: dict
) -> tuple[float, float, float, str]:
    line = next(
        l for l in registry["grid"]["lines"] if f"{l['from']}->{l['to']}" == params["line"]
    )
    added_mw = float(params["new_transfer_mw"]) - float(line["transfer_mw"])
    marginal = dispatch.marginal_cost(registry)

    # Deux effets distincts, additionnes: l'energie qui cesse d'etre non fournie
    # faute de transit, et le solaire local que l'antenne renforcee peut accueillir.
    ens = reliability.unserved_energy(registry)
    relieved_share = 0.08  # part du delestage national imputable a cette contrainte
    avoided_ens_kwh = ens["unserved_gwh"] * 1e6 * relieved_share
    voll = reliability.cost_of_unreliability(registry)["average_voll_xof_per_kwh"]

    hosted_solar_mw = min(added_mw * 0.5, 40.0)
    solar_kwh = hosted_solar_mw * 1000.0 * solar.specific_yield(registry, "mopti")
    solar_ppa = next(
        float(p["ppa_xof_per_kwh"])
        for p in registry["generation"]["plants"]
        if p["type"] == "solar_pv"
    )

    gain = avoided_ens_kwh * voll + solar_kwh * (marginal - solar_ppa)
    unserved_gwh = avoided_ens_kwh / 1e6
    rationale = (
        f"L'antenne 33 kV plafonne à {line['transfer_mw']:.0f} MW: le centre du pays est "
        "délesté faute de transit et n'a aucune marge pour accueillir du solaire. Le passage "
        f"en 150 kV dégage {added_mw:.0f} MW et rend raccordables environ "
        f"{hosted_solar_mw:.0f} MW de PV local."
    )
    return gain, unserved_gwh, gain, rationale


BENEFIT_MODELS = {
    "loss_reduction": _loss_reduction,
    "collection_improvement": _collection_improvement,
    "solar_fuel_displacement": _solar_fuel_displacement,
    "solar_bess_peak": _solar_bess_peak,
    "rental_exit": _rental_exit,
    "isolated_hybrid": _isolated_hybrid,
    "subsidy_targeting": _subsidy_targeting,
    "arrears_settlement": _arrears_settlement,
    "import_expansion": _import_expansion,
    "transmission_debottleneck": _transmission_debottleneck,
}


# ------------------------------------------------------------------ evaluation


def _blocking(registry: Registry, depends_on: list[str]) -> list[str]:
    statuses = {c["id"]: c["status"] for c in registry["reforms"]["structural_conditions"]}
    return [cid for cid in depends_on if statuses.get(cid) in ("manquant", "regression")]


def evaluate(registry: Registry, intervention: dict) -> Option:
    model = BENEFIT_MODELS.get(intervention["benefit_model"])
    if model is None:
        raise DataError(f"modèle de bénéfice inconnu: {intervention['benefit_model']}")
    benefit, unserved_gwh, relief, rationale = model(registry, intervention.get("params", {}))
    return Option(
        id=intervention["id"],
        name=intervention["name"],
        lever=intervention["lever"],
        annual_benefit_xof=benefit,
        capex_xof=float(intervention["capex_xof"]),
        lead_time_months=int(intervention["lead_time_months"]),
        risk=intervention["risk"],
        depends_on=list(intervention.get("depends_on", [])),
        unserved_gwh_addressed=unserved_gwh,
        subsidy_relief_xof=relief,
        rationale=rationale,
        source=intervention["source"],
        blocking_conditions=_blocking(registry, intervention.get("depends_on", [])),
    )


def portfolio(registry: Registry) -> list[Option]:
    """Toutes les options évaluées, classees par bénéfice ajusté du risque."""
    options = [evaluate(registry, item) for item in registry["interventions"]["interventions"]]
    options.sort(key=lambda o: o.risk_adjusted_benefit, reverse=True)
    return options


def by_category(registry: Registry) -> dict[str, list[Option]]:
    groups: dict[str, list[Option]] = {"sans regret": [], "conditionnel": [], "a preparer": []}
    for option in portfolio(registry):
        groups[option.category].append(option)
    return groups


def sequenced_plan(registry: Registry) -> list[dict]:
    """Séquence en trois horizons, avec pour chacun la condition de passage.

    L'horizon n'est pas une preference: il est impose par les délais de réalisation
    et par l'ordre des dépendances de réforme.
    """
    groups = by_category(registry)
    critical = reforms.critical_path(registry)

    horizons = [
        {
            "horizon": "0-18 mois — récupérer ce qui existe déjà",
            "logic": (
                "Aucune de ces mesures ne demande de capacité nouvelle. Elles portent sur "
                "l'énergie déjà produite et déjà vendue, et leur rendement est immédiat."
            ),
            "options": [o for o in groups["sans regret"] if o.lead_time_months <= 18],
        },
        {
            "horizon": "18-36 mois — substituer le carburant importé",
            "logic": (
                "Le solaire raccordé et la sortie des groupes loués attaquent le poste de "
                "coût dominant. Leur rendement suppose un acheteur solvable: c'est la "
                "condition à lever en parallèle, pas après."
            ),
            "options": [
                o
                for o in portfolio(registry)
                if 18 < o.lead_time_months <= 36
                or (o.category == "conditionnel" and o.lead_time_months <= 30)
            ],
        },
        {
            "horizon": "36 mois et au-delà — lever les contraintes physiques",
            "logic": (
                "Réseau de transport et interconnexion: ces ouvrages ne résolvent pas la "
                "crise courante mais déterminent si la décennie suivante se joue sur du "
                "solaire bon marché ou sur du diesel."
            ),
            "options": [o for o in portfolio(registry) if o.lead_time_months > 36],
        },
    ]
    for h in horizons:
        h["annual_benefit_xof"] = sum(o.risk_adjusted_benefit for o in h["options"])
        h["capex_xof"] = sum(o.capex_xof for o in h["options"])
    return [
        {
            "horizon": h["horizon"],
            "logic": h["logic"],
            "annual_benefit_xof": h["annual_benefit_xof"],
            "capex_xof": h["capex_xof"],
            "options": [o.id for o in h["options"]],
            "reform_prerequisites": critical[:3],
        }
        for h in horizons
    ]


def headline_findings(registry: Registry) -> list[str]:
    """Les constats que les données imposent, formules pour un décideur."""
    costs = tariff.cost_of_supply(registry)
    ens = reliability.unserved_energy(registry)
    unrel = reliability.cost_of_unreliability(registry)
    balance = dispatch.capacity_balance(registry)
    spread = solar.resource_spread(registry)
    ratio = reliability.reliability_gap_vs_supply_cost(registry)
    groups = by_category(registry)
    no_regret = sum(o.risk_adjusted_benefit for o in groups["sans regret"])

    return [
        (
            f"Chaque kWh vendu rapporte {costs['average_revenue_xof_per_kwh']:.0f} FCFA et en "
            f"coûte {costs['average_cost_xof_per_kwh']:.0f}. L'écart de "
            f"{costs['subsidy_xof_per_kwh']:.0f} FCFA/kWh n'est pas un choix tarifaire: c'est "
            f"une dette de {costs['annual_subsidy_xof'] / 1e9:,.0f} milliards FCFA par an qui se "
            "reporte sur le budget, puis sur les fournisseurs."
        ),
        (
            f"Le délestage a coûté environ {unrel['total_cost_xof'] / 1e9:,.0f} milliards FCFA à "
            f"l'économie sur douze mois, pour {ens['unserved_gwh']:,.0f} GWh non fournis "
            f"({ens['share_of_sales']:.1%} des ventes). Subir un kWh manquant coûte "
            f"{ratio['ratio']:.1f} fois plus cher que le produire au coût marginal: l'inaction "
            "est l'option la plus chère du tableau."
        ),
        (
            f"Le déficit est un déficit de puissance ferme, pas d'énergie: "
            f"{balance['available_firm_mw']:.0f} MW disponibles le soir contre "
            f"{balance['peak_demand_mw']:.0f} MW de pointe et "
            f"{balance['latent_peak_mw']:.0f} MW de demande latente. Ajouter du solaire sans "
            "stockage réduit la facture de carburant sans réduire le délestage du soir."
        ),
        (
            f"L'irradiation ne varie que de {spread['yield_spread_share']:.0%} entre le meilleur "
            "et le moins bon site du pays, alors que le coût de raccordement varie d'un facteur "
            f"{spread['interconnection_spread_ratio']:.0f}. Choisir un site pour son ensoleillement "
            "plutôt que pour son raccordement, c'est optimiser la variable la moins importante."
        ),
        (
            f"Les mesures sans regret identifiées valent {no_regret / 1e9:,.0f} milliards FCFA par "
            "an et ne dépendent d'aucune réforme non acquise. Elles portent sur l'énergie déjà "
            "produite: pertes, recouvrement, arriérés."
        ),
    ]
