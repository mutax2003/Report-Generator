"""Deterministic adversarial review of project-folder AI drafts (Cursor gate).

Claude Cowork / Codex may write narratives under ``ai_drafts/``. Cursor runs this
module (via ``agent_folder_report.py --mode review``) to flag blockers before
Apply or render. Never calls an LLM; never writes Excel or touches ReportEngine.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Soft signals that drafts may be LLM boilerplate or ungrounded.
_RED_FLAG_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bas an ai\b", "LLM self-reference"),
    (r"\bi cannot\b", "refusal / incomplete draft language"),
    (r"\bas an artificial intelligence\b", "LLM self-reference"),
    (r"\bi'm unable to\b", "refusal / incomplete draft language"),
    (r"\bhallucinat", "meta language about hallucination"),
    (r"\binvent(ed|ing)?\s+(lab|result|concentration|analyte)", "possible invent-admission"),
)

_CONFIRM_RE = re.compile(r"\[confirm\]", re.IGNORECASE)
_MAX_NARRATIVE_CHARS = 80_000
_MAX_SECTIONS = 40


@dataclass
class ReviewFinding:
    severity: str  # blocker | warning | info
    code: str
    message: str
    path: str = ""


@dataclass
class AdversarialReviewResult:
    report_type: str
    can_apply: bool
    can_render: bool
    findings: list[ReviewFinding] = field(default_factory=list)
    cursor_prompt: str = ""
    generated_at: str = ""

    @property
    def blockers(self) -> list[ReviewFinding]:
        return [f for f in self.findings if f.severity == "blocker"]

    @property
    def warnings(self) -> list[ReviewFinding]:
        return [f for f in self.findings if f.severity == "warning"]


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
        if len(raw) > _MAX_NARRATIVE_CHARS:
            return {"_truncated": True, "_size": len(raw)}
        data = json.loads(raw)
        return data if isinstance(data, dict) else {"_invalid": "not_object"}
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        return {"_invalid": str(e)[:200]}


def _review_narratives(drafts: Path, findings: list[ReviewFinding]) -> None:
    path = drafts / "narratives.json"
    data = _load_json(path)
    if data is None:
        findings.append(
            ReviewFinding(
                "info",
                "no_narratives",
                "No narratives.json - Cowork/enrich may not have drafted yet.",
                str(path.name),
            )
        )
        return
    if "_invalid" in data:
        findings.append(
            ReviewFinding(
                "blocker",
                "narratives_corrupt",
                f"narratives.json is not valid JSON: {data['_invalid']}",
                path.name,
            )
        )
        return
    if data.get("_truncated"):
        findings.append(
            ReviewFinding(
                "blocker",
                "narratives_too_large",
                f"narratives.json exceeds {_MAX_NARRATIVE_CHARS} characters.",
                path.name,
            )
        )
        return
    sections = data.get("sections")
    if not isinstance(sections, list) or not sections:
        findings.append(
            ReviewFinding(
                "warning",
                "narratives_empty",
                "narratives.json has no sections - nothing to Apply.",
                path.name,
            )
        )
        return
    if len(sections) > _MAX_SECTIONS:
        findings.append(
            ReviewFinding(
                "warning",
                "narratives_many_sections",
                f"Unusually many narrative sections ({len(sections)}).",
                path.name,
            )
        )
    for i, item in enumerate(sections[:_MAX_SECTIONS]):
        if not isinstance(item, dict):
            findings.append(
                ReviewFinding(
                    "blocker",
                    "narratives_bad_section",
                    f"Section index {i} is not an object.",
                    path.name,
                )
            )
            continue
        section = str(item.get("section", "")).strip() or f"section_{i}"
        text = str(item.get("text", "")).strip()
        sources = item.get("sources") or item.get("source_files") or []
        if not text:
            findings.append(
                ReviewFinding(
                    "warning",
                    "empty_section",
                    f"Section '{section}' has empty text.",
                    path.name,
                )
            )
            continue
        if not sources:
            findings.append(
                ReviewFinding(
                    "warning",
                    "ungrounded_section",
                    f"Section '{section}' has no sources / source_files - "
                    "Cursor should demand citations from source/ before Apply.",
                    path.name,
                )
            )
        confirms = len(_CONFIRM_RE.findall(text))
        if confirms:
            findings.append(
                ReviewFinding(
                    "warning",
                    "confirm_markers",
                    f"Section '{section}' has {confirms} [confirm] gap marker(s).",
                    path.name,
                )
            )
        lower = text.lower()
        for pattern, label in _RED_FLAG_PATTERNS:
            if re.search(pattern, lower):
                findings.append(
                    ReviewFinding(
                        "blocker",
                        "red_flag_prose",
                        f"Section '{section}': {label} - rewrite before Apply.",
                        path.name,
                    )
                )
                break


def _review_field_suggestions(drafts: Path, findings: list[ReviewFinding]) -> None:
    path = drafts / "excel_field_suggestions.json"
    data = _load_json(path)
    if data is None:
        return
    if "_invalid" in data:
        findings.append(
            ReviewFinding(
                "blocker",
                "suggestions_corrupt",
                f"excel_field_suggestions.json invalid: {data['_invalid']}",
                path.name,
            )
        )
        return
    fields = data.get("fields")
    if isinstance(fields, dict):
        for key, val in list(fields.items())[:80]:
            text = str(val or "")
            if re.search(r"\bas an ai\b", text, re.I):
                findings.append(
                    ReviewFinding(
                        "blocker",
                        "suggestion_llm_voice",
                        f"Field '{key}' looks like LLM boilerplate.",
                        path.name,
                    )
                )


def _review_preflight(
    resolved: Any,
    findings: list[ReviewFinding],
    *,
    core_files: tuple[bytes, bytes] | None = None,
) -> bool:
    from project_folder import run_preflight_for_folder

    try:
        pre = run_preflight_for_folder(resolved, core_files=core_files)
    except Exception as e:  # noqa: BLE001 — surface as blocker for agents
        findings.append(
            ReviewFinding(
                "blocker",
                "preflight_failed",
                f"Preflight could not run: {type(e).__name__}: {e}",
            )
        )
        return False
    can_generate = bool(getattr(pre, "can_generate", False))
    for err in list(getattr(pre, "errors", None) or [])[:30]:
        findings.append(
            ReviewFinding("blocker", "preflight_error", str(err), "preflight")
        )
    for warn in list(getattr(pre, "warnings", None) or [])[:25]:
        findings.append(
            ReviewFinding("warning", "preflight_warning", str(warn), "preflight")
        )
    coverage = getattr(pre, "coverage", None)
    missing = list(getattr(coverage, "missing_in_data", None) or [])[:40]
    for name in missing:
        findings.append(
            ReviewFinding(
                "warning",
                "missing_template_var",
                f"Template tag '{{{{ {name} }}}}' has no Excel/sidebar value yet.",
                "preflight",
            )
        )
    if not can_generate:
        findings.append(
            ReviewFinding(
                "blocker",
                "cannot_generate",
                "Preflight can_generate is false - fix Excel/template before render.",
                "preflight",
            )
        )
    return can_generate


def _cursor_adversarial_prompt(report_type: str, findings: list[ReviewFinding]) -> str:
    blockers = [f for f in findings if f.severity == "blocker"]
    warns = [f for f in findings if f.severity == "warning"]
    lines = [
        "You are Cursor performing adversarial review of Claude Cowork drafts",
        f"for Alberta ESA profile `{report_type}`.",
        "",
        "Hard rules:",
        "- Do NOT invent lab results, APECs, UWIs, or certificate numbers.",
        "- Do NOT modify engine.py or inject LLM into ReportEngine.",
        "- Fix drafts under ai_drafts/ only; Excel Apply only after user confirms.",
        "- Prefer citations to filenames under source/.",
        "",
        f"Deterministic blockers ({len(blockers)}):",
    ]
    for f in blockers[:20]:
        lines.append(f"- [{f.code}] {f.message}")
    if not blockers:
        lines.append("- (none)")
    lines.append("")
    lines.append(f"Warnings ({len(warns)}) — challenge Cowork prose against source PDFs:")
    for f in warns[:15]:
        lines.append(f"- [{f.code}] {f.message}")
    if not warns:
        lines.append("- (none)")
    lines.extend(
        [
            "",
            "Your tasks:",
            "1) Open ai_drafts/narratives.json and each cited source PDF.",
            "2) Strike any claim not supported by source text; add [confirm] gaps.",
            "3) For phase1_alberta: verify APEC / DWDA / Phase II recommendation coherence.",
            "4) Re-run: python scripts/agent_folder_report.py --folder <path> --mode review",
            "5) Only then ask user to confirm --mode apply-drafts and --mode render --package.",
            "",
            "Alberta briefs: ai.prompts.agent_brief(report_type) / agent_task_prompt('adversarial_review').",
        ]
    )
    return "\n".join(lines) + "\n"


def run_adversarial_review(resolved: Any) -> AdversarialReviewResult:
    """Scan folder drafts + preflight; write markdown/JSON under ai_drafts/."""
    from project_folder import atomic_write_text

    drafts = resolved.ai_drafts_dir
    drafts.mkdir(parents=True, exist_ok=True)
    report_type = str((resolved.meta or {}).get("report_type") or "phase1_alberta")
    findings: list[ReviewFinding] = []

    if not resolved.excel_path.is_file() or not resolved.template_path.is_file():
        findings.append(
            ReviewFinding(
                "blocker",
                "missing_core",
                "project_data.xlsx and template.docx are required.",
            )
        )

    source_pdfs = list(getattr(resolved.inventory, "source_pdfs", None) or [])
    if not source_pdfs:
        findings.append(
            ReviewFinding(
                "warning",
                "no_source_pdfs",
                "source/ has no PDFs - Cowork drafts cannot be grounded.",
                "source/",
            )
        )

    _review_narratives(drafts, findings)
    _review_field_suggestions(drafts, findings)
    core_files: tuple[bytes, bytes] | None = None
    try:
        core_files = resolved.read_core_files()
    except (OSError, FileNotFoundError, ValueError):
        core_files = None
    can_generate = _review_preflight(resolved, findings, core_files=core_files)

    has_blocker = any(f.severity == "blocker" for f in findings)
    can_apply = not has_blocker
    can_render = bool(can_generate) and not any(
        f.code
        in {"missing_core", "preflight_failed", "preflight_error", "cannot_generate"}
        for f in findings
    )

    cursor_prompt = _cursor_adversarial_prompt(report_type, findings)
    result = AdversarialReviewResult(
        report_type=report_type,
        can_apply=can_apply,
        can_render=can_render,
        findings=findings,
        cursor_prompt=cursor_prompt,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    md_lines = [
        "# Adversarial review (deterministic + Cursor gate)",
        "",
        f"Generated: `{result.generated_at}`",
        f"Profile: `{report_type}`",
        f"**can_apply:** {can_apply}  |  **can_render:** {can_render}",
        "",
        "Claude Cowork drafts narratives; Cursor challenges them before Apply/render.",
        "This file is advisory for agents — QP sign-off still required.",
        "",
        "## Blockers",
    ]
    if result.blockers:
        for f in result.blockers:
            md_lines.append(f"- **{f.code}** ({f.path}): {f.message}")
    else:
        md_lines.append("- None")
    md_lines.extend(["", "## Warnings"])
    if result.warnings:
        for f in result.warnings:
            md_lines.append(f"- **{f.code}** ({f.path}): {f.message}")
    else:
        md_lines.append("- None")
    infos = [f for f in findings if f.severity == "info"]
    if infos:
        md_lines.extend(["", "## Info"])
        for f in infos:
            md_lines.append(f"- **{f.code}**: {f.message}")
    md_lines.extend(
        [
            "",
            "## Cursor adversarial prompt",
            "",
            "```",
            cursor_prompt.rstrip(),
            "```",
            "",
            "## Next CLI steps",
            "",
            "```powershell",
            "# After Cursor fixes drafts:",
            "python scripts\\agent_folder_report.py --folder <path> --mode review",
            "python scripts\\agent_folder_report.py --folder <path> --mode apply-drafts",
            "python scripts\\agent_folder_report.py --folder <path> --mode render --package",
            "```",
            "",
        ]
    )
    atomic_write_text(
        drafts / "adversarial_review.md",
        "\n".join(md_lines),
        root=resolved.root,
    )
    payload = {
        "report_type": result.report_type,
        "can_apply": result.can_apply,
        "can_render": result.can_render,
        "generated_at": result.generated_at,
        "findings": [asdict(f) for f in result.findings],
        "cursor_prompt": result.cursor_prompt,
    }
    atomic_write_text(
        drafts / "adversarial_review.json",
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        root=resolved.root,
    )
    return result
