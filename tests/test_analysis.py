"""Tests des calculs decisionnels.

On verifie deux choses distinctes: que les formules sont justes (invariants
mathematiques verifiables a la main) et que les conclusions qualitatives que le
rapport enonce decoulent bien des donnees, pas d'une opinion codee en dur.
"""

import unittest

from malinergy.analysis import decisions, dispatch, lcoe, reforms, reliability, solar, tariff
from malinergy.datasets import DataError, load_registry


class TariffTests(unittest.TestCase):
    def setUp(self):
        self.r = load_registry()

    def test_block_pricing_is_marginal_not_average(self):
        # 100 kWh = 50 a 60 FCFA puis 50 a 82 FCFA.
        self.assertAlmostEqual(
            tariff.energy_charge(self.r, "bt_domestique", 100), 50 * 60 + 50 * 82
        )

    def test_first_block_only(self):
        self.assertAlmostEqual(tariff.energy_charge(self.r, "bt_domestique", 30), 30 * 60)

    def test_open_ended_last_block(self):
        base = 50 * 60 + 50 * 82 + 100 * 110
        self.assertAlmostEqual(
            tariff.energy_charge(self.r, "bt_domestique", 300), base + 100 * 133
        )

    def test_average_price_rises_with_consumption(self):
        ladder = tariff.bill_ladder(self.r)
        big = [row for row in ladder if row["kwh"] >= 100]
        prices = [row["average_price_xof_per_kwh"] for row in big]
        self.assertEqual(prices, sorted(prices))

    def test_social_tranche_is_vat_exempt(self):
        self.assertEqual(tariff.bill(self.r, "bt_social", 40).vat, 0.0)
        self.assertGreater(tariff.bill(self.r, "bt_domestique", 40).vat, 0.0)

    def test_negative_consumption_is_rejected(self):
        with self.assertRaises(ValueError):
            tariff.energy_charge(self.r, "bt_domestique", -5)

    def test_unknown_category_is_rejected(self):
        with self.assertRaises(DataError):
            tariff.category(self.r, "categorie_fantome")

    def test_cost_exceeds_revenue(self):
        costs = tariff.cost_of_supply(self.r)
        self.assertGreater(
            costs["average_cost_xof_per_kwh"], costs["average_revenue_xof_per_kwh"]
        )
        self.assertLess(costs["cost_recovery_ratio"], 1.0)

    def test_subsidy_shares_sum_to_one(self):
        rows = tariff.subsidy_incidence(self.r)
        self.assertAlmostEqual(sum(r["share_of_subsidy"] for r in rows), 1.0, places=6)

    def test_subsidy_is_poorly_targeted(self):
        # Le constat central du rapport: la tranche sociale rassemble beaucoup
        # d'abonnes et capte peu de subvention.
        eff = tariff.targeting_efficiency(self.r)
        self.assertLess(eff["share_to_social_tranche"], eff["social_customers_share"])
        self.assertLess(eff["targeting_ratio"], 1.0)


class SolarTests(unittest.TestCase):
    def setUp(self):
        self.r = load_registry()

    def test_specific_yield_is_plausible(self):
        for site in ("bamako", "gao", "sikasso"):
            y = solar.specific_yield(self.r, site)
            self.assertTrue(1400 < y < 2100, f"{site}: {y}")

    def test_capacity_factor_matches_yield(self):
        self.assertAlmostEqual(
            solar.capacity_factor(self.r, "segou"),
            solar.specific_yield(self.r, "segou") / 8760.0,
        )

    def test_northern_sites_carry_a_soiling_penalty(self):
        self.assertLess(
            solar.performance_ratio(self.r, "gao"), solar.performance_ratio(self.r, "bamako")
        )

    def test_best_resource_is_not_the_best_site(self):
        # Le point contre-intuitif du corpus: Kidal a la meilleure ressource et le
        # pire score, parce que l'evacuation domine.
        ranking = solar.rank_sites(self.r)
        best_resource = max(ranking, key=lambda s: s.specific_yield)
        self.assertNotEqual(ranking[0].id, best_resource.id)

    def test_isolated_sites_are_routed_to_hybridisation(self):
        for site in solar.rank_sites(self.r):
            if site.grid_km > 500:
                self.assertIn("hybride", site.verdict)

    def test_resource_spread_is_small_relative_to_connection_spread(self):
        spread = solar.resource_spread(self.r)
        self.assertLess(spread["yield_spread_share"], 0.2)
        self.assertGreater(spread["interconnection_spread_ratio"], 10)

    def test_unknown_site_is_rejected(self):
        with self.assertRaises(DataError):
            solar.site(self.r, "tombouctou-nord")


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.r = load_registry()

    def test_merit_order_is_sorted_by_variable_cost(self):
        costs = [e.variable_cost_xof_per_kwh for e in dispatch.merit_order(self.r)]
        self.assertEqual(costs, sorted(costs))

    def test_hydro_comes_first(self):
        self.assertEqual(dispatch.merit_order(self.r)[0].technology, "hydro")

    def test_dispatch_never_exceeds_availability(self):
        for entry in dispatch.merit_order(self.r):
            self.assertLessEqual(entry.dispatched_mw, entry.available_mw + 1e-9)

    def test_solar_absent_at_evening_peak(self):
        evening = {
            e.id: e.available_mw for e in dispatch.merit_order(self.r, solar_available=False)
        }
        day = {e.id: e.available_mw for e in dispatch.merit_order(self.r, solar_available=True)}
        self.assertEqual(evening["solaire_ipp"], 0.0)
        self.assertGreater(day["solaire_ipp"], 0.0)

    def test_firm_capacity_is_short_of_peak(self):
        balance = dispatch.capacity_balance(self.r)
        self.assertLess(balance["firm_margin_mw"], 0)
        self.assertGreater(
            balance["latent_firm_gap_mw"],
            balance["peak_demand_mw"] - balance["available_firm_mw"],
        )

    def test_marginal_cost_is_the_dearest_dispatched_unit(self):
        stack = dispatch.merit_order(self.r, solar_available=False)
        dispatched = [e for e in stack if e.dispatched_mw > 0]
        self.assertEqual(
            dispatch.marginal_cost(self.r), max(e.variable_cost_xof_per_kwh for e in dispatched)
        )

    def test_marginal_cost_falls_when_demand_falls(self):
        low = dispatch.marginal_cost(self.r, 200.0)
        high = dispatch.marginal_cost(self.r, 620.0)
        self.assertLess(low, high)

    def test_loss_reduction_value_scales_linearly(self):
        one = dispatch.loss_reduction_value(self.r, 1.0)["total_value_xof"]
        three = dispatch.loss_reduction_value(self.r, 3.0)["total_value_xof"]
        self.assertAlmostEqual(three, one * 3, places=2)

    def test_solar_displacement_is_profitable_against_thermal(self):
        value = dispatch.displacement_value(self.r, 100.0, site="segou")
        self.assertGreater(value["net_saving_xof_per_kwh"], 0)


class LcoeTests(unittest.TestCase):
    def setUp(self):
        self.r = load_registry()

    def test_capital_recovery_factor_against_known_value(self):
        # 8 % sur 20 ans = 0,101852...
        self.assertAlmostEqual(lcoe.capital_recovery_factor(0.08, 20), 0.1018522, places=6)

    def test_zero_rate_is_straight_line(self):
        self.assertAlmostEqual(lcoe.capital_recovery_factor(0.0, 25), 0.04)

    def test_components_sum_to_total(self):
        r = lcoe.compute(self.r, "pv_utility", site="segou")
        self.assertAlmostEqual(
            r.total, r.capital_component + r.fixed_opex_component + r.fuel_component
        )

    def test_solar_beats_rented_diesel(self):
        pv = lcoe.compute(self.r, "pv_utility", site="segou")
        rental = lcoe.compute(self.r, "location_diesel_nouvelle")
        self.assertLess(pv.total, rental.total)

    def test_rented_diesel_is_import_exposed(self):
        self.assertTrue(lcoe.compute(self.r, "location_diesel_nouvelle").is_import_exposed)
        self.assertFalse(lcoe.compute(self.r, "pv_utility", site="segou").is_import_exposed)

    def test_higher_wacc_raises_capital_intensive_lcoe(self):
        sens = lcoe.sensitivity(self.r, "pv_utility", site="segou")
        values = [row["lcoe"] for row in sens["wacc"]]
        self.assertEqual(values, sorted(values))
        self.assertEqual(sens["dominant_driver"], "coût du capital")

    def test_fuel_price_drives_thermal_not_solar(self):
        thermal = lcoe.sensitivity(self.r, "hfo_neuf")
        self.assertEqual(thermal["dominant_driver"], "prix du carburant")

    def test_efficiency_is_not_an_lcoe(self):
        with self.assertRaises(DataError):
            lcoe.compute(self.r, "reduction_pertes")

    def test_ranking_is_ordered(self):
        totals = [r.total for r in lcoe.ranking(self.r, site="segou")]
        self.assertEqual(totals, sorted(totals))


class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.r = load_registry()

    def test_series_is_chronological_and_complete(self):
        months = [row["month"] for row in reliability.series(self.r)]
        self.assertEqual(months, sorted(months))
        self.assertGreaterEqual(len(months), 36)

    def test_unserved_energy_is_a_minority_of_sales(self):
        ens = reliability.unserved_energy(self.r)
        self.assertTrue(0 < ens["share_of_sales"] < 0.5)

    def test_critical_window_is_the_dry_season(self):
        # Etiage et pointe de climatisation coincident: mars a juin.
        window = reliability.critical_window(self.r)
        self.assertTrue(set(window) <= {3, 4, 5, 6})
        self.assertIn(5, window)

    def test_shedding_worsened_over_the_series(self):
        years = reliability.by_year(self.r)
        self.assertLess(years[0].unserved_gwh, years[-2].unserved_gwh)

    def test_unserved_energy_costs_more_than_supplying_it(self):
        ratio = reliability.reliability_gap_vs_supply_cost(self.r)
        self.assertGreater(ratio["ratio"], 1.0)

    def test_backup_generation_is_dearer_than_the_grid(self):
        backup = reliability.backup_generation_cost(self.r)
        costs = tariff.cost_of_supply(self.r)
        self.assertGreater(backup["genset_cost_xof_per_kwh"], costs["average_cost_xof_per_kwh"])

    def test_business_bears_most_of_the_cost(self):
        cost = reliability.cost_of_unreliability(self.r)
        self.assertGreater(cost["business_cost_xof"], cost["household_cost_xof"])


class ReformTests(unittest.TestCase):
    def setUp(self):
        self.r = load_registry()

    def test_timeline_is_ordered(self):
        years = [e["year"] for e in reforms.timeline(self.r)]
        self.assertEqual(years, sorted(years))

    def test_completion_index_is_a_share(self):
        self.assertTrue(0.0 <= reforms.completion_index(self.r) <= 1.0)

    def test_gaps_exclude_acquired_conditions(self):
        for gap in reforms.gaps(self.r):
            self.assertNotEqual(gap.status, "acquis")

    def test_gaps_are_ordered_by_leverage(self):
        leverage = [g.leverage for g in reforms.gaps(self.r)]
        self.assertEqual(leverage, sorted(leverage, reverse=True))

    def test_critical_path_covers_every_gap(self):
        self.assertEqual(
            set(reforms.critical_path(self.r)), {g.id for g in reforms.gaps(self.r)}
        )

    def test_critical_path_respects_dependencies(self):
        path = reforms.critical_path(self.r)
        position = {cid: i for i, cid in enumerate(path)}
        for gap in reforms.gaps(self.r):
            for unlocked in gap.unlocks:
                if unlocked in position:
                    self.assertLess(
                        position[gap.id],
                        position[unlocked],
                        f"{gap.id} doit preceder {unlocked}",
                    )

    def test_reversals_are_reported(self):
        stats = reforms.cadence(self.r)
        self.assertGreater(stats["reversal_rate"], 0)
        self.assertTrue(stats["reversed"])


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.r = load_registry()

    def test_every_intervention_evaluates(self):
        options = decisions.portfolio(self.r)
        self.assertEqual(len(options), len(self.r["interventions"]["interventions"]))

    def test_every_option_has_a_positive_benefit(self):
        for option in decisions.portfolio(self.r):
            self.assertGreater(option.annual_benefit_xof, 0, option.id)

    def test_portfolio_is_ordered_by_risk_adjusted_benefit(self):
        values = [o.risk_adjusted_benefit for o in decisions.portfolio(self.r)]
        self.assertEqual(values, sorted(values, reverse=True))

    def test_risk_discount_reduces_benefit(self):
        for option in decisions.portfolio(self.r):
            self.assertLess(option.risk_adjusted_benefit, option.annual_benefit_xof)

    def test_blocked_options_are_conditional(self):
        for option in decisions.portfolio(self.r):
            if option.blocking_conditions:
                self.assertEqual(option.category, "conditionnel")

    def test_blocking_conditions_are_really_missing(self):
        statuses = {c["id"]: c["status"] for c in self.r["reforms"]["structural_conditions"]}
        for option in decisions.portfolio(self.r):
            for cid in option.blocking_conditions:
                self.assertIn(statuses[cid], ("manquant", "regression"))

    def test_every_option_carries_a_rationale_and_a_source(self):
        for option in decisions.portfolio(self.r):
            self.assertTrue(option.rationale.strip(), option.id)
            self.r.source(option.source)

    def test_categories_partition_the_portfolio(self):
        groups = decisions.by_category(self.r)
        total = sum(len(v) for v in groups.values())
        self.assertEqual(total, len(decisions.portfolio(self.r)))

    def test_plan_horizons_are_populated(self):
        plan = decisions.sequenced_plan(self.r)
        self.assertEqual(len(plan), 3)
        for step in plan:
            self.assertTrue(step["horizon"])
            self.assertTrue(step["reform_prerequisites"])

    def test_findings_reference_computed_values(self):
        findings = decisions.headline_findings(self.r)
        self.assertGreaterEqual(len(findings), 5)
        for finding in findings:
            self.assertTrue(any(ch.isdigit() for ch in finding))

    def test_unknown_benefit_model_is_rejected(self):
        with self.assertRaises(DataError):
            decisions.evaluate(
                self.r,
                {
                    "id": "x",
                    "name": "x",
                    "lever": "x",
                    "benefit_model": "inexistant",
                    "capex_xof": 0,
                    "lead_time_months": 1,
                    "risk": "faible",
                    "source": "malinergy-estimation",
                },
            )


if __name__ == "__main__":
    unittest.main()
