"""Guided workflow step index (no separate UI — sections in layout.py)."""

from __future__ import annotations

from ui.layout import compute_workflow_step


def render_workflow_step(
    *,
    has_excel: bool,
    has_template: bool,
    preflight_ok: bool | None,
    has_output: bool,
) -> int:
    """Return current 1-based step (upload → pre-flight → generate → download)."""
    return compute_workflow_step(
        has_excel=has_excel,
        has_template=has_template,
        preflight_ok=preflight_ok,
        has_output=has_output,
    )
