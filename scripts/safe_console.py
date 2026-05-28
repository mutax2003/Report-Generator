"""Windows-safe stdout for CLI scripts (avoids UnicodeEncodeError on cp1252)."""

from __future__ import annotations

import sys


def safe_print(*parts: object, **kwargs: object) -> None:
    """Print text; replace characters the console cannot encode."""
    sep = str(kwargs.get("sep", " "))
    end = str(kwargs.get("end", "\n"))
    file = kwargs.get("file", sys.stdout)
    text = sep.join(str(p) for p in parts) + end
    enc = getattr(file, "encoding", None) or "utf-8"
    try:
        file.write(text)
    except UnicodeEncodeError:
        file.write(text.encode(enc, errors="replace").decode(enc, errors="replace"))
    if kwargs.get("flush"):
        file.flush()
