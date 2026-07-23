"""Verify documented unit test count matches unittest discover."""

from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Canonical documented count — update when adding/removing tests.
DOCUMENTED_TEST_COUNT = 392
DOCUMENTED_SKIP_COUNT = 4
DOCUMENTED_HEALTH_CHECK_COUNT = 18

DOC_FILES = [
    ROOT / "AGENTS.md",
    ROOT / "README.md",
    ROOT / "docs" / "01-overview.md",
    ROOT / "docs" / "08-testing.md",
    ROOT / "docs" / "17-server-update-runbook.md",
    ROOT / ".cursor" / "rules" / "esa-report-generator-architecture.mdc",
    ROOT / ".cursor" / "rules" / "esa-testing-ci.mdc",
]

HEALTH_DOC_FILES = [
    ROOT / "AGENTS.md",
    ROOT / "README.md",
    ROOT / "docs" / "05-developer-guide.md",
    ROOT / "docs" / "08-testing.md",
    ROOT / "docs" / "14-deployment.md",
    ROOT / "docs" / "17-server-update-runbook.md",
    ROOT / ".cursor" / "rules" / "esa-report-generator-architecture.mdc",
]


def discover_test_count() -> tuple[int, int]:
    loader = unittest.TestLoader()
    suite = loader.discover(str(ROOT / "tests"), pattern="test_*.py")
    count = suite.countTestCases()
    skipped = 0

    def _walk(tests: unittest.TestSuite | unittest.TestCase) -> None:
        nonlocal skipped
        if isinstance(tests, unittest.TestSuite):
            for child in tests:
                _walk(child)
            return
        method_name = getattr(tests, "_testMethodName", None)
        if not method_name:
            return
        method = getattr(tests, method_name, None)
        if method and getattr(method, "__unittest_skip__", False):
            skipped += 1

    _walk(suite)
    return count, skipped


def check_documented_count(expected: int) -> list[str]:
    pattern = re.compile(r"\b(\d{3})\s+tests?\b", re.IGNORECASE)
    errors: list[str] = []
    for path in DOC_FILES:
        if not path.is_file():
            errors.append(f"Missing doc file: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            found = int(match.group(1))
            if found != expected:
                errors.append(
                    f"{path.relative_to(ROOT)}: documents {found} tests, expected {expected}"
                )
    return errors


def check_documented_health_checks(expected: int) -> list[str]:
    """Catch docs that still say 17 checks when health_check has 18."""
    patterns = (
        re.compile(r"\b(\d{2})\s*[-/]?\s*(?:step\s+)?(?:regression\s+)?checks?\b", re.I),
        re.compile(r"\b(\d{2})/(\d{2})\s+passed\b", re.I),
        re.compile(r"\b(\d{2})-step\s+(?:regression|health)\b", re.I),
    )
    word_steps = {
        "seventeen": 17,
        "eighteen": 18,
    }
    word_pat = re.compile(
        r"\b(seventeen|eighteen)[-\s]+step\b",
        re.I,
    )
    errors: list[str] = []
    for path in HEALTH_DOC_FILES:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for pat in patterns:
            for match in pat.finditer(text):
                nums = [int(g) for g in match.groups() if g and g.isdigit()]
                for found in nums:
                    if found in (17, 18) and found != expected:
                        errors.append(
                            f"{path.relative_to(ROOT)}: documents {found} health checks, "
                            f"expected {expected} ({match.group(0)!r})"
                        )
        for match in word_pat.finditer(text):
            found = word_steps[match.group(1).lower()]
            if found != expected:
                errors.append(
                    f"{path.relative_to(ROOT)}: documents {found} health checks, "
                    f"expected {expected} ({match.group(0)!r})"
                )
    return errors


def main() -> int:
    actual, skipped = discover_test_count()
    print(f"Discovered: {actual} tests ({skipped} methods marked skip)")
    print(f"Documented: {DOCUMENTED_TEST_COUNT} tests ({DOCUMENTED_SKIP_COUNT} may skip)")

    failed = False
    if actual != DOCUMENTED_TEST_COUNT:
        print(
            f"FAIL — update DOCUMENTED_TEST_COUNT in count_tests.py and doc files "
            f"({DOCUMENTED_TEST_COUNT} -> {actual})"
        )
        failed = True
    else:
        print("PASS — discovered count matches DOCUMENTED_TEST_COUNT")

    if skipped > DOCUMENTED_SKIP_COUNT:
        print(
            f"FAIL — discovered skip markers ({skipped}) exceed "
            f"DOCUMENTED_SKIP_COUNT ({DOCUMENTED_SKIP_COUNT})"
        )
        failed = True
    else:
        print(
            f"PASS — skip markers ({skipped}) within DOCUMENTED_SKIP_COUNT "
            f"({DOCUMENTED_SKIP_COUNT})"
        )

    doc_errors = check_documented_count(DOCUMENTED_TEST_COUNT)
    for err in doc_errors:
        print(f"FAIL — {err}")
        failed = True
    if not doc_errors and actual == DOCUMENTED_TEST_COUNT:
        print("PASS — all doc files reference the canonical test count")

    health_errors = check_documented_health_checks(DOCUMENTED_HEALTH_CHECK_COUNT)
    for err in health_errors:
        print(f"FAIL — {err}")
        failed = True
    if not health_errors:
        print(
            f"PASS — health-check docs match DOCUMENTED_HEALTH_CHECK_COUNT "
            f"({DOCUMENTED_HEALTH_CHECK_COUNT})"
        )

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
