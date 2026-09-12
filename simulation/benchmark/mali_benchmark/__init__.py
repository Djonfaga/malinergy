"""Cross-tool comparison for the Malian power system study."""

from .capability import hand_written_work, matrix, scores
from .compare import compare, provenance
from .effort import access_table, effort_table
from .findings import by_confidence, headline
from .findings import table as findings_table

__version__ = "1.0.0"
__all__ = [
    "access_table",
    "by_confidence",
    "compare",
    "effort_table",
    "build_figures",
    "findings_table",
    "hand_written_work",
    "headline",
    "matrix",
    "provenance",
    "scores",
]
