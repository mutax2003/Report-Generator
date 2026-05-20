"""Extract MERGEFIELD names from a Word .docx (for mapping to Excel)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from security import ZipReadBudget, open_docx_zip, read_docx_xml_member  # noqa: E402


def extract_merge_fields(docx_path: Path) -> list[str]:
    data = docx_path.read_bytes()
    fields: set[str] = set()
    with open_docx_zip(data) as zf:
        budget = ZipReadBudget()
        for name in zf.namelist():
            if not name.endswith(".xml"):
                continue
            try:
                xml = read_docx_xml_member(zf, name, budget)
            except (KeyError, OSError):
                continue
            for m in re.finditer(r"MERGEFIELD\s+([^\s\\]+)", xml, re.IGNORECASE):
                fields.add(m.group(1).strip('"'))
    return sorted(fields, key=str.lower)


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "22xxxxR Phase 2 ESA Full_merge.docx"
    )
    if not path.is_file():
        print(f"Not found: {path}", file=sys.stderr)
        return 1
    fields = extract_merge_fields(path)
    print(f"{path.name}: {len(fields)} MERGEFIELD(s)\n")
    for f in fields:
        print(f)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
