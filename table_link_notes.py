"""
Narrative caveats for tables whose rows could not be linked to the current site.

``engine`` records link-filter problems in ``ctx["_table_link_issues"]`` as
``{loop_var: {"status": "unmatched" | "partial", "sheet": str, "column": str}}``:

- ``unmatched`` — a multi-site workbook links table rows to sites, but no row
  matches this site, so the table is empty in this report.
- ``partial`` — some rows matched, but rows with a blank link cell were left out.

Auto-generated narrative must then not state that nothing exceeded criteria; it
uses :func:`link_caveat` instead.
"""

from __future__ import annotations

from typing import Any

LINK_ISSUES_KEY = "_table_link_issues"
_NARRATIVE_STATUSES = ("unmatched", "partial")


def link_issue(ctx: dict[str, Any], *loop_vars: str) -> dict[str, Any] | None:
    """First narrative-relevant link issue for any of ``loop_vars`` (or None)."""
    issues = ctx.get(LINK_ISSUES_KEY)
    if not isinstance(issues, dict):
        return None
    for loop_var in loop_vars:
        info = issues.get(loop_var)
        if isinstance(info, dict) and info.get("status") in _NARRATIVE_STATUSES:
            return info
    return None


def link_caveat(info: dict[str, Any], what: str = "Laboratory results") -> str:
    """Sentence (no trailing period) replacing an absence-of-exceedance statement."""
    sheet = str(info.get("sheet") or "the linked sheet")
    column = str(info.get("column") or "link")
    if info.get("status") == "partial":
        return (
            f"Some {what[:1].lower() + what[1:]} could not be matched to this site "
            f"(blank {column} cells in {sheet}) — review the {sheet} link column; "
            "conclusions below may be incomplete"
        )
    return (
        f"{what} could not be matched to this site — review the {sheet} link column "
        f"({column}); no conclusion about exceedances has been drawn"
    )
