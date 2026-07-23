"""Build Windows-friendly HTML help pack under help/ from key docs/*.md files."""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (anchor_id, title, markdown_path relative to repo)
HELP_PAGES: list[tuple[str, str, str]] = [
    ("start", "Start here", "docs/00-start-here.md"),
    ("user-guide", "User guide", "docs/02-user-guide.md"),
    ("excel", "Excel data guide", "docs/03-excel-data-guide.md"),
    ("templates", "Template authoring", "docs/04-template-authoring.md"),
    ("phase1", "Alberta Phase I ESA", "docs/11-alberta-phase1-esa.md"),
    ("folder", "Project folder workflow", "docs/22-project-folder-workflow.md"),
    ("ai", "AI assistant", "docs/09-ai-assistant.md"),
    ("shortcuts", "Keyboard shortcuts", ""),  # generated
]


def _inline_md(text: str) -> str:
    """Escape text and apply simple [label](url) links."""
    parts: list[str] = []
    last = 0
    for m in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", text):
        parts.append(html.escape(text[last : m.start()]))
        parts.append(
            f'<a href="{html.escape(m.group(2), quote=True)}">'
            f"{html.escape(m.group(1))}</a>"
        )
        last = m.end()
    parts.append(html.escape(text[last:]))
    return "".join(parts)


def _md_to_simple_html(text: str) -> str:
    """Minimal markdown → HTML (headings, paragraphs, lists, fenced code)."""
    lines = text.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    in_ul = False
    in_code = False
    para: list[str] = []

    def flush_para() -> None:
        nonlocal para
        if para:
            out.append("<p>" + _inline_md(" ".join(para)) + "</p>")
            para = []

    def end_ul() -> None:
        nonlocal in_ul
        if in_ul:
            out.append("</ul>")
            in_ul = False

    for line in lines:
        if line.strip().startswith("```"):
            flush_para()
            end_ul()
            if in_code:
                out.append("</code></pre>")
                in_code = False
            else:
                out.append("<pre><code>")
                in_code = True
            continue
        if in_code:
            out.append(html.escape(line) + "\n")
            continue
        if not line.strip():
            flush_para()
            end_ul()
            continue
        heading = re.match(r"^(#{1,3})\s+(.*)$", line)
        if heading:
            flush_para()
            end_ul()
            level = len(heading.group(1))
            out.append(f"<h{level}>{html.escape(heading.group(2))}</h{level}>")
            continue
        if re.match(r"^[-*]\s+", line):
            flush_para()
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            item = re.sub(r"^[-*]\s+", "", line)
            out.append(f"<li>{_inline_md(item)}</li>")
            continue
        if re.match(r"^\|", line) or re.match(r"^---+", line.strip()):
            flush_para()
            end_ul()
            continue
        end_ul()
        para.append(line.strip())

    flush_para()
    end_ul()
    if in_code:
        out.append("</code></pre>")
    return "\n".join(out)


_CSS = """
:root { --slate:#2e3540; --magenta:#b24292; --bg:#f4f6f8; }
body { font-family: Segoe UI, Tahoma, sans-serif; margin:0; color:#1a1a1a; background:#fff; }
.layout { display:flex; min-height:100vh; }
nav {
  width:240px; background:var(--slate); color:#e8eaed; padding:1rem;
  flex-shrink:0;
}
nav h1 { font-size:1.05rem; margin:0 0 0.75rem; color:#fff; }
nav a { color:#e8b8d9; text-decoration:none; display:block; padding:0.35rem 0; }
nav a:hover { color:#fff; }
main { flex:1; padding:1.5rem 2rem; max-width:900px; background:var(--bg); }
main section {
  background:#fff; border:1px solid #dde1e6; border-radius:6px;
  padding:1.25rem 1.5rem; margin-bottom:1.25rem;
}
h2 { color:var(--slate); border-bottom:3px solid var(--magenta); padding-bottom:0.35rem; }
pre { background:#1e1e1e; color:#d4d4d4; padding:0.75rem; overflow:auto; border-radius:4px; }
code { font-family: Consolas, monospace; font-size:0.9em; }
table { border-collapse:collapse; width:100%; }
td, th { border:1px solid #ccc; padding:0.4rem 0.6rem; text-align:left; }
kbd {
  font-family: Consolas, monospace; background:#eee; border:1px solid #bbb;
  border-radius:3px; padding:0.1rem 0.35rem; font-size:0.85em;
}
.footer { color:#666; font-size:0.85rem; margin-top:2rem; }
"""


def _shortcuts_html() -> str:
    return """
<h2 id="shortcuts">Keyboard shortcuts</h2>
<p>The ESA Report Generator shows a Windows-style menu bar (File, Edit, View, Tools, Help).
On a <strong>local desktop</strong> install, press <strong>F1</strong> to open this help file.
On <strong>Streamlit Community Cloud</strong> (hosted mode), F1 cannot open local
<code>file://</code> help — use the in-app <strong>Help &amp; documentation</strong>
expander on the Report tab instead.</p>
<table>
<tr><th>Action</th><th>How</th></tr>
<tr><td>Help contents (desktop)</td><td><kbd>F1</kbd> (global) or Help → Contents</td></tr>
<tr><td>Help contents (Cloud)</td><td>Report tab → Help &amp; documentation expander</td></tr>
<tr><td>Open / focus project folder</td><td>File menu (desktop only; hidden when hosted)</td></tr>
<tr><td>Load Alberta Phase I sample</td><td>File menu</td></tr>
<tr><td>Clear generated outputs</td><td>File menu</td></tr>
<tr><td>Toggle Simple mode</td><td>Edit menu</td></tr>
<tr><td>Glossary</td><td>View menu</td></tr>
</table>
<p>Only <strong>F1</strong> is hooked globally in the browser. Use the menus for other actions.</p>
"""


def build_help(root: Path | None = None) -> Path:
    root = root or ROOT
    help_dir = root / "help"
    help_dir.mkdir(parents=True, exist_ok=True)

    sections: list[str] = []
    nav_links: list[str] = []

    for anchor, title, rel in HELP_PAGES:
        nav_links.append(f'<a href="#{anchor}">{html.escape(title)}</a>')
        if anchor == "shortcuts":
            sections.append(f'<section id="{anchor}">{_shortcuts_html()}</section>')
            continue
        path = root / rel
        if not path.is_file():
            sections.append(
                f'<section id="{anchor}"><h2>{html.escape(title)}</h2>'
                f"<p><em>Document missing: {html.escape(rel)}</em></p></section>"
            )
            continue
        body = _md_to_simple_html(path.read_text(encoding="utf-8"))
        sections.append(
            f'<section id="{anchor}"><h2>{html.escape(title)}</h2>\n{body}\n</section>'
        )

    index = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>ESA Report Generator Help</title>
  <style>{_CSS}</style>
</head>
<body>
  <div class="layout">
    <nav>
      <h1>ESA Report Generator</h1>
      <p style="font-size:0.85rem;color:#9aa3ad;">Ecoventure Inc. Help</p>
      {"".join(nav_links)}
    </nav>
    <main>
      {"".join(sections)}
      <p class="footer">Created by Andrew Liu, Ecoventure Inc., Copyright 2026 · Desktop: F1 opens this help; Cloud: use in-app Help &amp; documentation.</p>
    </main>
  </div>
</body>
</html>
"""
    out = help_dir / "index.html"
    out.write_text(index, encoding="utf-8")
    (help_dir / "README.md").write_text(
        "# Help pack\n\nGenerated by `python scripts/build_help.py`.\n"
        "Desktop: **Help → Contents** or **F1**. "
        "Cloud/hosted: Report tab **Help & documentation** expander "
        "(F1 `file://` does not work).\n",
        encoding="utf-8",
    )
    return out


def main() -> int:
    path = build_help()
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
