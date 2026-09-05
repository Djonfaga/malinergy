"""Tests du rendu PDF.

Le rendu dépend de reportlab et des polices DejaVu, tous deux optionnels: les tests
se désactivent proprement si l'environnement ne les fournit pas, plutôt que
d'échouer sur une absence qui n'est pas un défaut du code.
"""

import tempfile
import unittest
from pathlib import Path

from malinergy import pdf, report
from malinergy.datasets import load_registry

try:
    import reportlab  # noqa: F401

    HAS_REPORTLAB = True
except ModuleNotFoundError:  # pragma: no cover - dépend de l'environnement
    HAS_REPORTLAB = False

HAS_FONTS = pdf._font_dir() is not None


class MarkdownParsingTests(unittest.TestCase):
    """Le découpage du Markdown ne dépend d'aucune bibliothèque externe."""

    def test_headings_are_levelled(self):
        blocks = list(pdf._blocks("# Titre\n\n## Section\n\n### Sous-section\n"))
        self.assertEqual([kind for kind, _ in blocks], ["h1", "h2", "h3"])

    def test_table_is_parsed_with_header_and_rows(self):
        markdown = "| a | b |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n"
        (kind, (header, rows)), = list(pdf._blocks(markdown))
        self.assertEqual(kind, "table")
        self.assertEqual(header, ["a", "b"])
        self.assertEqual(rows, [["1", "2"], ["3", "4"]])

    def test_bullets_and_numbers_are_distinguished(self):
        blocks = dict(list(pdf._blocks("- un\n- deux\n\n1. a\n2. b\n")))
        self.assertIn("bullets", blocks)
        self.assertIn("numbers", blocks)
        self.assertEqual(blocks["numbers"], ["a", "b"])

    def test_paragraph_lines_are_joined(self):
        (kind, text), = list(pdf._blocks("une phrase\ncoupée en deux\n"))
        self.assertEqual(kind, "para")
        self.assertEqual(text, "une phrase coupée en deux")

    def test_blockquote_is_captured(self):
        (kind, text), = list(pdf._blocks("> une citation\n> sur deux lignes\n"))
        self.assertEqual(kind, "quote")
        self.assertEqual(text, "une citation sur deux lignes")

    def test_inline_markup_is_converted(self):
        self.assertIn("<b>gras</b>", pdf._inline("**gras**"))
        self.assertIn("Malinergy-Mono", pdf._inline("`code`"))

    def test_angle_brackets_are_escaped_before_markup(self):
        # Sans échappement, un chevron dans les données casserait le balisage.
        self.assertIn("&lt;", pdf._inline("a < b"))
        self.assertNotIn("<b", pdf._inline("a < b"))

    def test_separator_detection(self):
        self.assertTrue(pdf._is_separator("|---|---|"))
        self.assertTrue(pdf._is_separator("|:--|--:|"))
        self.assertFalse(pdf._is_separator("| a | b |"))


@unittest.skipUnless(HAS_REPORTLAB and HAS_FONTS, "reportlab ou polices DejaVu absents")
class RenderTests(unittest.TestCase):
    def setUp(self):
        self.registry = load_registry()

    def test_report_renders_to_a_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "rapport.pdf"
            written = pdf.build(report.build(self.registry), target)
            self.assertEqual(written, target)
            self.assertTrue(target.exists())
            self.assertGreater(target.stat().st_size, 20_000)
            self.assertEqual(target.read_bytes()[:5], b"%PDF-")

    def test_parent_directory_is_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "profond" / "dossier" / "rapport.pdf"
            pdf.build("# Titre\n\nUn paragraphe accentué: éèàôû.\n", target)
            self.assertTrue(target.exists())


if __name__ == "__main__":
    unittest.main()
