"""Le garde-fou du depot: aucun chiffre sans source, aucun agregat incoherent."""

import json
import unittest
from pathlib import Path

from malinergy.datasets import DATASET_FILES, DataError, Registry, load_registry


class TestRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = load_registry()

    def test_all_datasets_load(self):
        for name in DATASET_FILES:
            self.assertIn(name, self.registry.documents)

    def test_validation_is_clean(self):
        self.assertEqual(self.registry.validate(), [])

    def test_every_source_reference_resolves(self):
        # validate() leve deja, mais on verifie que le registre lui-meme est complet.
        for source in self.registry.sources.values():
            self.assertTrue(source.title)
            self.assertTrue(source.url)
            self.assertIn(source.confidence, ("haute", "moyenne", "faible"))

    def test_unknown_source_is_rejected(self):
        documents = {k: json.loads(json.dumps(v)) for k, v in self.registry.documents.items()}
        documents["solar"]["sites"][0]["source"] = "source-inventee"
        with self.assertRaises(DataError):
            Registry(documents=documents).validate()

    def test_sales_cannot_exceed_generation(self):
        documents = {k: json.loads(json.dumps(v)) for k, v in self.registry.documents.items()}
        documents["sector"]["aggregates"]["sales_gwh_year"]["value"] = 99999.0
        with self.assertRaises(DataError):
            Registry(documents=documents).validate()

    def test_sales_mix_sums_to_one(self):
        documents = {k: json.loads(json.dumps(v)) for k, v in self.registry.documents.items()}
        documents["tariffs"]["sales_mix"][0]["share_of_sales"] += 0.1
        with self.assertRaises(DataError):
            Registry(documents=documents).validate()

    def test_scalar_requires_a_sourced_value(self):
        with self.assertRaises(DataError):
            self.registry.scalar("sector", "aggregates")

    def test_missing_directory_is_reported(self):
        with self.assertRaises(DataError):
            load_registry(Path("/repertoire/inexistant"))

    def test_provenance_summary_counts_every_reference(self):
        counts = self.registry.provenance_summary()
        self.assertGreater(sum(counts.values()), 50)
        self.assertGreater(counts["haute"], 0)

    def test_estimates_are_declared_as_such(self):
        # Une valeur estimee ne doit jamais se presenter comme un releve officiel.
        estimate = self.registry.source("malinergy-estimation")
        self.assertTrue(estimate.is_estimate)
        self.assertEqual(estimate.confidence, "faible")


if __name__ == "__main__":
    unittest.main()
