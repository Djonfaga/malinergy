"""Tests du corpus externe et de la réconciliation.

L'enjeu de ces tests n'est pas seulement l'exactitude des calculs: c'est que le
mécanisme de réconciliation ne puisse pas être neutralisé par inadvertance. Une
divergence qui cesse d'être signalée est pire qu'une divergence.
"""

import unittest

from malinergy.analysis import corpus, decisions, tariff
from malinergy.datasets import DataError, load_registry


class CorpusTests(unittest.TestCase):
    def setUp(self):
        self.r = load_registry()

    def test_every_observation_has_a_declared_source(self):
        for obs in corpus.observations(self.r):
            self.r.source(obs.source)

    def test_observations_carry_units_and_years(self):
        for obs in corpus.observations(self.r):
            self.assertTrue(obs.unit, obs.id)
            self.assertGreater(obs.year, 1950, obs.id)

    def test_corpus_includes_non_mali_comparators(self):
        # Les jeux mondiaux où le Mali n'est qu'une ligne servent de comparateurs.
        self.assertTrue(corpus.coverage(self.r)["comparators"])

    def test_unknown_observation_is_rejected(self):
        with self.assertRaises(DataError):
            corpus.observation(self.r, "observation-fantome")

    def test_coverage_counts_match_the_dataset(self):
        cov = corpus.coverage(self.r)
        self.assertEqual(cov["count"], len(self.r["observations"]["observations"]))
        self.assertGreater(cov["reconcilable"], 5)


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.r = load_registry()

    def test_reconciliation_runs_for_every_flagged_observation(self):
        flagged = [o for o in self.r["observations"]["observations"] if "reconcile" in o]
        self.assertEqual(len(corpus.reconcile(self.r)), len(flagged))

    def test_results_are_ordered_by_absolute_gap(self):
        gaps = [abs(r.relative_gap) for r in corpus.reconcile(self.r)]
        self.assertEqual(gaps, sorted(gaps, reverse=True))

    def test_verdict_follows_the_tolerance(self):
        for row in corpus.reconcile(self.r):
            self.assertEqual(row.agrees, abs(row.relative_gap) <= row.tolerance)

    def test_divergences_and_confirmations_partition_the_results(self):
        total = len(corpus.divergences(self.r)) + len(corpus.confirmations(self.r))
        self.assertEqual(total, len(corpus.reconcile(self.r)))

    def test_every_divergence_is_documented(self):
        # Une divergence non expliquée est un bug de curation, pas un résultat.
        for row in corpus.divergences(self.r):
            self.assertTrue(row.resolution.strip(), row.observation)

    def test_score_is_a_share(self):
        self.assertTrue(0.0 <= corpus.reconciliation_score(self.r) <= 1.0)

    def test_manantali_share_matches_the_published_allocation(self):
        row = next(r for r in corpus.reconcile(self.r) if r.observation == "omvs_mw_mali")
        self.assertTrue(row.agrees)

    def test_average_revenue_matches_the_imf_figure(self):
        # Le prix de vente moyen calculé à partir de la grille doit retrouver la
        # valeur publiée par le FMI: c'est le contrôle croisé du modèle tarifaire.
        row = next(r for r in corpus.reconcile(self.r) if r.observation == "prix_vente_moyen_edm")
        self.assertTrue(row.agrees)
        self.assertAlmostEqual(row.internal, tariff.average_revenue_per_kwh(self.r))

    def test_unknown_reconciliation_kind_is_rejected(self):
        with self.assertRaises(DataError):
            corpus._internal_value(self.r, {"kind": "inexistant"})

    def test_unknown_computed_metric_is_rejected(self):
        with self.assertRaises(DataError):
            corpus._computed_metric(self.r, "metrique-fantome")


class SubsidyLayeringTests(unittest.TestCase):
    """La subvention budgétaire et la ponction totale sont deux grandeurs distinctes."""

    def setUp(self):
        self.r = load_registry()
        self.costs = tariff.cost_of_supply(self.r)

    def test_drain_exceeds_the_budget_line(self):
        self.assertGreater(self.costs["annual_fiscal_drain_xof"], self.costs["annual_subsidy_xof"])

    def test_off_budget_share_is_the_difference(self):
        self.assertAlmostEqual(
            self.costs["off_budget_xof"],
            self.costs["annual_fiscal_drain_xof"] - self.costs["annual_subsidy_xof"],
        )

    def test_full_cost_exceeds_average_cost(self):
        self.assertGreater(
            self.costs["full_cost_xof_per_kwh"], self.costs["average_cost_xof_per_kwh"]
        )

    def test_cost_recovery_stays_below_one(self):
        self.assertLess(self.costs["cost_recovery_ratio"], 1.0)


class ComparativeTests(unittest.TestCase):
    def setUp(self):
        self.r = load_registry()

    def test_mali_consumes_less_than_every_comparator(self):
        gap = corpus.energy_poverty_gap(self.r)
        for scope, data in gap["comparators"].items():
            self.assertGreater(data["multiple"], 1.0, scope)

    def test_mini_grid_customers_pay_more_than_grid_customers(self):
        inequity = corpus.tariff_inequity(self.r)
        self.assertGreater(inequity["ratio_mini_grid_to_grid"], 1.0)
        self.assertGreater(inequity["ratio_mini_grid_to_social"], 1.0)

    def test_captive_mining_capacity_is_material(self):
        captive = corpus.captive_capacity(self.r)
        self.assertGreater(captive["total_operating_mw"], 100)
        self.assertGreater(captive["ratio_to_edm_thermal"], 0.2)
        self.assertGreater(captive["solar_share"], 0.0)

    def test_captive_excludes_projects_not_yet_built(self):
        captive = corpus.captive_capacity(self.r)
        self.assertGreater(captive["planned_solar_mw"], 0)

    def test_fuel_exposure_is_a_majority_of_firm_capacity(self):
        security = corpus.fuel_security(self.r)
        self.assertGreater(security["share_of_firm_capacity"], 0.4)
        self.assertLessEqual(security["share_of_firm_capacity"], 1.0)

    def test_options_declare_their_fuel_exposure_reduction(self):
        for option in decisions.portfolio(self.r):
            self.assertGreaterEqual(option.fuel_exposure_reduction_mw, 0.0)
        total = sum(o.fuel_exposure_reduction_mw for o in decisions.portfolio(self.r))
        self.assertGreater(total, 0.0)

    def test_findings_cover_the_corpus_conclusions(self):
        findings = decisions.headline_findings(self.r)
        self.assertGreaterEqual(len(findings), 9)
        joined = " ".join(findings)
        for token in ("camions-citernes", "mines", "mini-réseau", "kWh par habitant"):
            self.assertIn(token, joined)


if __name__ == "__main__":
    unittest.main()
