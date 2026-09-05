"""Tests de la restitution: rapport, export JSON et interface en ligne de commande."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from malinergy import cli, export, report
from malinergy.datasets import load_registry


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.r = load_registry()
        self.markdown = report.build(self.r)

    def test_all_sections_present(self):
        for heading in (
            "## Ce que les données imposent",
            "## Tarifs, coûts et subventions",
            "## Offre: ordre de mérite",
            "## Délestage",
            "## Ressource solaire",
            "## Coût complet des options",
            "## Séquence des réformes",
            "## Que faire, dans quel ordre",
            "## Provenance et limites",
        ):
            self.assertIn(heading, self.markdown)

    def test_report_states_its_limits(self):
        self.assertIn("malinergy-estimation", self.markdown)
        self.assertIn("jamais des relevés officiels", self.markdown)

    def test_markdown_tables_are_well_formed(self):
        for line in self.markdown.splitlines():
            if line.startswith("|") and not set(line) <= set("|- "):
                self.assertTrue(line.rstrip().endswith("|"), line)


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.r = load_registry()

    def test_payloads_are_json_serialisable(self):
        for name, payload in export.build_payloads(self.r).items():
            json.dumps(payload, ensure_ascii=False, default=str)

    def test_headline_metrics_carry_provenance(self):
        for metric in export.headline_metrics(self.r):
            self.assertTrue(metric["source"])
            self.assertIn(metric["confidence"], ("haute", "moyenne", "faible"))

    def test_write_produces_every_document(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = export.write(self.r, tmp)
            names = {p.name for p in paths}
            self.assertIn("metrics.json", names)
            self.assertIn("decisions.json", names)
            for path in paths:
                document = json.loads(Path(path).read_text(encoding="utf-8"))
                self.assertIn("data", document)
                self.assertIn("snapshot", document)

    def test_export_is_deterministic(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            export.write(self.r, a)
            export.write(self.r, b)
            for path in sorted(Path(a).iterdir()):
                self.assertEqual(
                    path.read_text(encoding="utf-8"),
                    (Path(b) / path.name).read_text(encoding="utf-8"),
                )


class CliTests(unittest.TestCase):
    def _run(self, argv):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli.main(argv)
        return code, buffer.getvalue()

    def test_validation_command(self):
        code, out = self._run(["valider"])
        self.assertEqual(code, 0)
        self.assertIn("cohérents", out)

    def test_bill_command(self):
        code, out = self._run(["facture", "150"])
        self.assertEqual(code, 0)
        self.assertIn("Prix moyen", out)

    def test_every_read_only_command_runs(self):
        for command in (
            "sources",
            "tarifs",
            "offre",
            "lcoe",
            "solaire",
            "delestage",
            "reformes",
            "decisions",
        ):
            code, out = self._run([command])
            self.assertEqual(code, 0, command)
            self.assertTrue(out.strip(), command)

    def test_report_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "rapport.md"
            code, _ = self._run(["rapport", "--sortie", str(target)])
            self.assertEqual(code, 0)
            self.assertIn("# Malinergy", target.read_text(encoding="utf-8"))

    def test_export_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = self._run(["export", "--sortie", tmp])
            self.assertEqual(code, 0)
            self.assertIn("metrics.json", out)

    def test_json_section_command(self):
        code, out = self._run(["json", "decisions"])
        self.assertEqual(code, 0)
        json.loads(out)

    def test_unknown_json_section_fails(self):
        code, _ = self._run(["json", "inexistant"])
        self.assertEqual(code, 2)

    def test_missing_data_directory_fails_cleanly(self):
        code, _ = self._run(["--donnees", "/pas/un/repertoire", "valider"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
