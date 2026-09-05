"""Rendu PDF du rapport de décision.

Le rapport existe déjà en Markdown; ce module en produit une version imprimable qui
respecte le système graphique du site — mêmes couleurs, même hiérarchie
typographique, mêmes conventions de tableau.

``reportlab`` est une dépendance optionnelle: le reste de la plateforme fonctionne
sans elle. Installer avec ``pip install 'malinergy[pdf]'``.
"""

from __future__ import annotations

import re
from pathlib import Path

# Palette du Malinergy Design System (src/styles/colors_and_type.css).
INDIGO_950 = "#0B1838"
INDIGO_700 = "#24449B"
OCHRE_700 = "#CD8117"
CLAY_700 = "#AD4935"
BONE_100 = "#FBF8F2"
BONE_200 = "#F5EFE1"
BONE_300 = "#E8E0CE"
INK_950 = "#14120B"
INK_600 = "#6B6452"

# DejaVu couvre les accents français et le tiret cadratin, que les polices intégrées
# de reportlab ignorent. Les emplacements varient selon la distribution.
FONT_DIRS = (
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/share/fonts/dejavu"),
    Path("/usr/local/share/fonts/dejavu"),
    Path("/Library/Fonts"),
)
FONT_FILES = {
    "Malinergy": "DejaVuSans.ttf",
    "Malinergy-Bold": "DejaVuSans-Bold.ttf",
    "Malinergy-Serif": "DejaVuSerif.ttf",
    "Malinergy-SerifBold": "DejaVuSerif-Bold.ttf",
    "Malinergy-Mono": "DejaVuSansMono.ttf",
    # DejaVu ne fournit pas d'oblique pour le Sans: l'emphase passe par le serif,
    # visuellement distinct et toujours présent dans le même paquet.
    "Malinergy-Italic": "DejaVuSerif.ttf",
}


def _font_dir() -> Path | None:
    for directory in FONT_DIRS:
        if all((directory / name).exists() for name in set(FONT_FILES.values())):
            return directory
    return None


class PdfUnavailable(RuntimeError):
    """reportlab n'est pas installé, ou les polices Unicode sont introuvables."""


def _require_reportlab():
    try:
        import reportlab  # noqa: F401
    except ModuleNotFoundError as exc:  # pragma: no cover - dépend de l'environnement
        raise PdfUnavailable(
            "le rendu PDF demande reportlab: pip install 'malinergy[pdf]'"
        ) from exc


def _register_fonts() -> bool:
    """Enregistre les polices Unicode. Retourne False si elles sont absentes.

    Les polices intégrées de reportlab ne couvrent pas les accents français ni le
    tiret cadratin: sans DejaVu, le rendu serait faux plutôt que dégradé.
    """
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.fonts import addMapping

    directory = _font_dir()
    if directory is None:
        return False
    for name, filename in FONT_FILES.items():
        pdfmetrics.registerFont(TTFont(name, str(directory / filename)))
    addMapping("Malinergy", 0, 0, "Malinergy")
    addMapping("Malinergy", 1, 0, "Malinergy-Bold")
    addMapping("Malinergy", 0, 1, "Malinergy-Italic")
    addMapping("Malinergy", 1, 1, "Malinergy-Bold")
    return True


# ------------------------------------------------------------------- Markdown

INLINE_CODE = re.compile(r"`([^`]+)`")
BOLD = re.compile(r"\*\*([^*]+)\*\*")
LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def _inline(text: str) -> str:
    """Convertit le balisage en ligne du Markdown vers celui de reportlab."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = BOLD.sub(r"<b>\1</b>", text)
    text = INLINE_CODE.sub(
        rf'<font name="Malinergy-Mono" size="8.5" color="{CLAY_700}">\1</font>', text
    )
    text = LINK.sub(rf'<font color="{INDIGO_700}">\1</font>', text)
    return text


def _split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_separator(line: str) -> bool:
    return bool(line.strip()) and set(line.strip()) <= set("|-: ")


def _blocks(markdown: str):
    """Découpe le Markdown en blocs typés, dans l'ordre du document."""
    lines = markdown.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped.startswith("|") and i + 1 < len(lines) and _is_separator(lines[i + 1]):
            header = _split_row(stripped)
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(_split_row(lines[i]))
                i += 1
            yield ("table", (header, rows))
            continue

        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            yield (f"h{min(level, 3)}", stripped.lstrip("#").strip())
            i += 1
            continue

        if stripped.startswith(">"):
            quote = [stripped.lstrip(">").strip()]
            i += 1
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip().lstrip(">").strip())
                i += 1
            yield ("quote", " ".join(q for q in quote if q))
            continue

        if stripped.startswith(("- ", "* ")):
            items = []
            while i < len(lines) and lines[i].strip().startswith(("- ", "* ")):
                items.append(lines[i].strip()[2:])
                i += 1
            yield ("bullets", items)
            continue

        if re.match(r"^\d+\.\s", stripped):
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s", lines[i].strip()):
                items.append(re.sub(r"^\d+\.\s", "", lines[i].strip()))
                i += 1
            yield ("numbers", items)
            continue

        para = [stripped]
        i += 1
        while (
            i < len(lines)
            and lines[i].strip()
            and not lines[i].strip().startswith(("#", "|", ">", "- ", "* "))
        ):
            para.append(lines[i].strip())
            i += 1
        yield ("para", " ".join(para))


# ----------------------------------------------------------------------- rendu


def _styles():
    from reportlab.lib.enums import TA_JUSTIFY
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "MalTitle",
            parent=base["Title"],
            fontName="Malinergy-SerifBold",
            fontSize=24,
            leading=29,
            textColor=INDIGO_950,
            alignment=0,
            spaceAfter=6,
        ),
        "h2": ParagraphStyle(
            "MalH2",
            fontName="Malinergy-SerifBold",
            fontSize=15,
            leading=19,
            textColor=INDIGO_950,
            spaceBefore=20,
            spaceAfter=7,
        ),
        "h3": ParagraphStyle(
            "MalH3",
            fontName="Malinergy-Bold",
            fontSize=11,
            leading=14,
            textColor=OCHRE_700,
            spaceBefore=13,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "MalBody",
            fontName="Malinergy",
            fontSize=9,
            leading=13.5,
            textColor=INK_950,
            alignment=TA_JUSTIFY,
            spaceAfter=7,
        ),
        "bullet": ParagraphStyle(
            "MalBullet",
            fontName="Malinergy",
            fontSize=9,
            leading=13.5,
            textColor=INK_950,
            leftIndent=12,
            bulletIndent=2,
            spaceAfter=3,
        ),
        "quote": ParagraphStyle(
            "MalQuote",
            fontName="Malinergy-Italic",
            fontSize=9,
            leading=13.5,
            textColor=INK_600,
            leftIndent=14,
            borderPadding=0,
            spaceBefore=5,
            spaceAfter=8,
        ),
        "cell": ParagraphStyle(
            "MalCell", fontName="Malinergy", fontSize=7.2, leading=9.4, textColor=INK_950
        ),
        "cellhead": ParagraphStyle(
            "MalCellHead",
            fontName="Malinergy-Bold",
            fontSize=7.2,
            leading=9.4,
            textColor=INDIGO_950,
        ),
        "caption": ParagraphStyle(
            "MalCaption",
            fontName="Malinergy-Mono",
            fontSize=7.5,
            leading=11,
            textColor=INK_600,
            spaceAfter=14,
        ),
    }


def _table_flowable(header, rows, styles, width):
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Table, TableStyle

    data = [[Paragraph(_inline(c), styles["cellhead"]) for c in header]]
    data += [[Paragraph(_inline(c), styles["cell"]) for c in row] for row in rows]

    columns = len(header)
    # La première colonne porte le libellé: elle reçoit une part double.
    weights = [2.0] + [1.0] * (columns - 1) if columns > 2 else [1.0] * columns
    total = sum(weights)
    widths = [width * w / total for w in weights]

    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(BONE_200)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(INDIGO_950)),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor(INDIGO_950)),
                ("GRID", (0, 1), (-1, -1), 0.25, colors.HexColor(BONE_300)),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(BONE_300)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(BONE_100)]),
            ]
        )
    )
    return table


def _decorations(canvas, doc):
    """Bandeau de pied de page: identité, pagination."""
    from reportlab.lib import colors

    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor(BONE_300))
    canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, 42, doc.pagesize[0] - doc.rightMargin, 42)
    canvas.setFont("Malinergy-Mono", 7)
    canvas.setFillColor(colors.HexColor(INK_600))
    canvas.drawString(
        doc.leftMargin, 31, "Malinergy — plateforme de connaissances sur l'énergie au Mali"
    )
    canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 31, str(canvas.getPageNumber()))
    canvas.restoreState()


def build(markdown: str, path: Path | str, *, subtitle: str = "") -> Path:
    """Rend le Markdown du rapport en PDF et retourne le chemin écrit."""
    _require_reportlab()

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

    if not _register_fonts():
        searched = ", ".join(str(d) for d in FONT_DIRS)
        raise PdfUnavailable(
            f"polices DejaVu introuvables ({searched}): le rendu des accents serait faux"
        )

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(target),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title="Malinergy — rapport de décision sur le secteur électrique malien",
        author="Malinergy",
        subject="Secteur énergétique malien: données sourcées et analyse d'aide à la décision",
    )
    styles = _styles()
    story = []
    width = doc.width

    for kind, payload in _blocks(markdown):
        if kind == "h1":
            story.append(Paragraph(_inline(payload), styles["title"]))
        elif kind == "h2":
            story.append(Paragraph(_inline(payload), styles["h2"]))
        elif kind == "h3":
            story.append(Paragraph(_inline(payload), styles["h3"]))
        elif kind == "para":
            style = styles["caption"] if payload.startswith("Instantané") else styles["body"]
            story.append(Paragraph(_inline(payload), style))
        elif kind == "quote":
            story.append(Paragraph(_inline(payload), styles["quote"]))
        elif kind in ("bullets", "numbers"):
            numbered = kind == "numbers"
            items = [
                ListItem(
                    Paragraph(_inline(text), styles["bullet"]),
                    leftIndent=16,
                    value=index if numbered else None,
                )
                for index, text in enumerate(payload, start=1)
            ]
            story.append(
                ListFlowable(
                    items,
                    bulletType="1" if numbered else "bullet",
                    bulletFontName="Malinergy-Bold" if numbered else "Malinergy",
                    bulletFontSize=8.5 if numbered else 6,
                    bulletColor=OCHRE_700,
                    bulletOffsetY=-1 if numbered else -2,
                    start=1 if numbered else None,
                    leftIndent=16,
                )
            )
            story.append(Spacer(1, 6))
        elif kind == "table":
            header, rows = payload
            story.append(_table_flowable(header, rows, styles, width))
            story.append(Spacer(1, 10))

    if subtitle:
        story.insert(1, Paragraph(_inline(subtitle), styles["caption"]))

    doc.build(story, onFirstPage=_decorations, onLaterPages=_decorations)
    return target
