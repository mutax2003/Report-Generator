"""Classify PDF files into Phase I appendix labels A–H (heuristic + optional LLM)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from ai.client import complete_text

APPENDIX_LABELS = frozenset("ABCDEFGH")
AUTO_GENERATED_APPENDIX_LABELS = frozenset({"A", "D", "G"})

_FILENAME_HINTS: list[tuple[str, str]] = [
    (r"abadata|spill.?search|spillsearch", "B"),
    (r"air.?photo|aerial|orthophoto", "C"),
    (r"drilling.?waste|waste.?checklist|directive.?050", "D"),
    (r"survey|plan|legal.?survey", "E"),
    (r"land.?title|title.?search|pin", "F"),
    (r"calc.?table|waste.?calc|volume.?table", "G"),
    (r"sketch|site.?plan|location.?map|figure", "H"),
    (r"qp.?decl|professional.?decl|declaration", "A"),
]


@dataclass
class AppendixClassification:
    path: Path
    label: str
    confidence: float
    source: str
    rationale: str = ""

    def to_dict(self) -> dict[str, str | float | bool]:
        return {
            "filename": self.path.name,
            "label": self.label,
            "confidence": round(self.confidence, 2),
            "source": self.source,
            "rationale": self.rationale,
            "auto_generated_at_render": self.label in AUTO_GENERATED_APPENDIX_LABELS,
        }


def heuristic_appendix_label(path: Path) -> str:
    """Fast filename-only label for appendices/ uploads (no LLM)."""
    hit = _heuristic_label(path)
    if hit:
        return hit.label
    stem = path.stem.upper()
    if len(stem) == 1 and stem in APPENDIX_LABELS:
        return stem
    return "B"


def _heuristic_label(path: Path) -> AppendixClassification | None:
    name = path.name.lower()
    for pattern, label in _FILENAME_HINTS:
        if re.search(pattern, name, re.I):
            return AppendixClassification(
                path=path,
                label=label,
                confidence=0.85,
                source="heuristic",
                rationale=f"Filename matches appendix {label} pattern",
            )
    return None


def _llm_classify(paths: list[Path]) -> dict[str, AppendixClassification]:
    if not paths:
        return {}
    listing = [{"filename": p.name, "size_kb": p.stat().st_size // 1024} for p in paths]
    raw = complete_text(
        system=(
            "Classify each PDF into one appendix label A–H for Alberta Phase I ESA packages. "
            "A=QP declaration, B=ABADATA spill search, C=air photos, D=drilling waste checklist, "
            "E=survey plan, F=land title, G=waste calc tables, H=site sketch. "
            "Return JSON array: [{\"filename\":\"...\",\"label\":\"B\",\"confidence\":0.9,\"rationale\":\"...\"}]"
        ),
        user=json.dumps(listing),
        json_mode=True,
    )
    if not raw:
        return {}
    try:
        rows = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if isinstance(rows, dict):
        rows = rows.get("items") or rows.get("classifications") or []
    by_name: dict[str, AppendixClassification] = {}
    name_to_path = {p.name: p for p in paths}
    for row in rows:
        if not isinstance(row, dict):
            continue
        fname = str(row.get("filename", "")).strip()
        label = str(row.get("label", "B")).upper()[:1]
        if label not in APPENDIX_LABELS or fname not in name_to_path:
            continue
        by_name[fname] = AppendixClassification(
            path=name_to_path[fname],
            label=label,
            confidence=float(row.get("confidence", 0.6)),
            source="llm",
            rationale=str(row.get("rationale", ""))[:200],
        )
    return by_name


def _annotate_auto_generated(item: AppendixClassification) -> AppendixClassification:
    if item.label in AUTO_GENERATED_APPENDIX_LABELS:
        item.rationale = (
            f"{item.rationale} Appendix {item.label} is auto-generated at render — "
            "place B/C/E/F/H PDFs in appendices/ instead."
        ).strip()
    return item


def classify_appendix_pdfs(
    pdfs: list[Path],
    *,
    use_llm: bool = True,
) -> list[AppendixClassification]:
    """Suggest appendix label per PDF; heuristics first, LLM fills gaps."""
    results: list[AppendixClassification] = []
    unresolved: list[Path] = []
    for pdf in pdfs:
        hit = _heuristic_label(pdf)
        if hit:
            results.append(hit)
        else:
            unresolved.append(pdf)

    llm_map: dict[str, AppendixClassification] = {}
    if use_llm and unresolved:
        llm_map = _llm_classify(unresolved)

    for pdf in unresolved:
        if pdf.name in llm_map:
            results.append(llm_map[pdf.name])
        else:
            results.append(
                AppendixClassification(
                    path=pdf,
                    label="B",
                    confidence=0.35,
                    source="default",
                    rationale="No filename match; default B — confirm manually",
                )
            )

    return [_annotate_auto_generated(r) for r in sorted(results, key=lambda r: (r.label, r.path.name))]
