"""Find bracket/underscore placeholder-like text in docx body."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from security import ZipReadBudget, open_docx_zip, read_docx_xml_member  # noqa: E402


def body_text(docx_path: Path) -> str:
    data = docx_path.read_bytes()
    parts: list[str] = []
    with open_docx_zip(data) as zf:
        budget = ZipReadBudget()
        for name in zf.namelist():
            if not name.startswith("word/") or not name.endswith(".xml"):
                continue
            try:
                xml = read_docx_xml_member(zf, name, budget)
            except (KeyError, OSError):
                continue
            for m in re.finditer(r"<w:t[^>]*>([^<]*)</w:t>", xml):
                t = m.group(1).strip()
                if t:
                    parts.append(t)
    return " ".join(parts)


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "22xxxxR Phase 2 ESA Full_merge.docx"
    )
    if not path.is_file():
        print(f"Not found: {path}", file=sys.stderr)
        return 1
    text = body_text(path)
    patterns = [
        (r"\[[A-Za-z0-9 _/-]{3,50}\]", "brackets"),
        (r"\{\{[^}]+\}\}", "jinja"),
        (r"XXX+", "xxx"),
        (r"x{4,}", "xxxx"),
        (r"INSERT\s+[A-Z][A-Z\s]{2,30}", "INSERT"),
        (r"TBD", "TBD"),
    ]
    for pat, label in patterns:
        hits = sorted(set(re.findall(pat, text, re.I)))
        if hits:
            print(f"\n{label} ({len(hits)}):")
            for h in hits[:30]:
                print(f"  {h}")
            if len(hits) > 30:
                print(f"  ... +{len(hits) - 30} more")
    print("\nFirst 200 chars of body text:")
    print(text[:200].replace("\n", " "))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
