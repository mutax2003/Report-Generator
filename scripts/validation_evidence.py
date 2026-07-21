#!/usr/bin/env python3
"""Generate validation evidence package mapping tests to production requirements."""

from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUTPUT = ROOT / "docs" / "validation_evidence.json"

REQUIREMENTS = [
    {
        "id": "REQ-001",
        "title": "Excel + Word render produces valid DOCX",
        "sources": ["docs/00-start-here.md", "engine.py"],
        "tests": ["tests.test_render_e2e", "tests.test_render_path_parity"],
    },
    {
        "id": "REQ-002",
        "title": "Upload validation and safe errors",
        "sources": ["security.py", "docs/07-security-and-deployment.md"],
        "tests": ["tests.test_security", "tests.test_upload_helpers"],
    },
    {
        "id": "REQ-003",
        "title": "DWDA / SED compliance appendices",
        "sources": ["docs/21-dwda-directive-050-compliance.md", "appendix_generator.py"],
        "tests": ["tests.test_dwda_compliance", "tests.test_sed002_compliance", "tests.test_appendix_generator"],
    },
    {
        "id": "REQ-004",
        "title": "Deliverable package manifest and provenance",
        "sources": ["deliverable_pack.py", "provenance.py"],
        "tests": ["tests.test_deliverable_pack", "tests.test_provenance"],
    },
    {
        "id": "REQ-005",
        "title": "Streamlit UX smoke and generate flow",
        "sources": ["app.py", "ui/results.py"],
        "tests": ["tests.test_streamlit_smoke", "tests.test_layout"],
    },
    {
        "id": "REQ-006",
        "title": "HTTP headless render service",
        "sources": ["automate/http_server.py", "automate/render.py"],
        "tests": ["tests.test_http_server", "tests.test_automate_render"],
    },
    {
        "id": "REQ-007",
        "title": "Audit trail integrity",
        "sources": ["audit_trail.py"],
        "tests": ["tests.test_audit_trail"],
    },
    {
        "id": "REQ-008",
        "title": "QP e-signature verification",
        "sources": ["qp_signature.py"],
        "tests": ["tests.test_qp_signature"],
    },
]


def _discovered_tests() -> set[str]:
    loader = unittest.TestLoader()
    suite = loader.discover(str(ROOT / "tests"), pattern="test_*.py")
    names: set[str] = set()

    def walk(node: unittest.TestSuite) -> None:
        for child in node:
            if isinstance(child, unittest.TestSuite):
                walk(child)
            else:
                mod = child.__class__.__module__
                names.add(mod)
                if mod.startswith("test_"):
                    names.add(f"tests.{mod}")

    walk(suite)
    return names


def build_evidence() -> dict[str, object]:
    discovered = _discovered_tests()
    rows = []
    for req in REQUIREMENTS:
        matched = [t for t in req["tests"] if t in discovered]
        rows.append(
            {
                **req,
                "tests_found": matched,
                "covered": len(matched) == len(req["tests"]),
            }
        )
    covered = sum(1 for r in rows if r["covered"])
    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "requirements_total": len(rows),
        "requirements_covered": covered,
        "coverage_pct": round(100.0 * covered / len(rows), 1) if rows else 0.0,
        "requirements": rows,
    }


def main() -> int:
    evidence = build_evidence()
    OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT} ({evidence['requirements_covered']}/{evidence['requirements_total']} covered)")
    return 0 if evidence["requirements_covered"] == evidence["requirements_total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
