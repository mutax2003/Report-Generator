"""List Jinja2 placeholders in a .docx template."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from security import validate_template_upload  # noqa: E402
from template_tools import scan_template  # noqa: E402


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "22xxxxR Phase 2 ESA Full_merge.docx"
    if not path.is_file():
        print(f"Not found: {path}", file=sys.stderr)
        return 1
    data = path.read_bytes()
    validate_template_upload(data)
    scan = scan_template(data)
    print(f"Template: {path.name}\n")
    print("Root context variables ({{ var }}):")
    for v in sorted(scan.root_vars):
        print(f"  {v}")
    print(f"\nAll {{ }} expressions ({len(scan.mustache_exprs)}):")
    for v in sorted(scan.mustache_exprs):
        print(f"  {v}")
    print(f"\nBlock tags ({len(scan.block_tags)}):")
    for v in sorted(scan.block_tags):
        print(f"  {v}")
    if scan.split_issues:
        print(f"\nSplit-tag warnings ({len(scan.split_issues)}):")
        for issue in scan.split_issues:
            print(f"  {issue}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
