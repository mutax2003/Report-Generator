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
DOCUMENTED_TEST_COUNT = 284
DOCUMENTED_SKIP_COUNT = 3

DOC_FILES = [
    ROOT / "AGENTS.md",
    ROOT / "README.md",
    ROOT / "docs" / "08-testing.md",
    ROOT / ".cursor" / "rules" / "esa-report-generator-architecture.mdc",
    ROOT / ".cursor" / "rules" / "esa-testing-ci.mdc",
]


def discover_test_count() -> tuple[int, int]:
    loader = unittest.TestLoader()
    suite = loader.discover(str(ROOT / "tests"), pattern="test_*.py")
    count = suite.countTestCases()
    skipped = 0
    for case in suite:
        if getattr(case, "__class__", None):
            for method_name in dir(case):
                if not method_name.startswith("test"):
                    continue
                method = getattr(case, method_name, None)
                if method and getattr(method, "__unittest_skip__", False):
                    skipped += 1
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

    doc_errors = check_documented_count(DOCUMENTED_TEST_COUNT)
    for err in doc_errors:
        print(f"FAIL — {err}")
        failed = True
    if not doc_errors and actual == DOCUMENTED_TEST_COUNT:
        print("PASS — all doc files reference the canonical test count")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
