"""Native folder picker for local Streamlit desktop use."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def folder_picker_available() -> bool:
    """True when a native folder dialog can be shown on this host."""
    if sys.platform in ("win32", "darwin"):
        return True
    return bool(os.environ.get("DISPLAY"))


def pick_local_folder(*, initial: str = "", title: str = "Select project folder") -> str | None:
    """
    Open the OS folder picker; return an absolute path, or None if cancelled.

    Requires a graphical desktop (local Windows/macOS/Linux). Unavailable in
    headless Docker — callers should fall back to manual path entry.
    """
    if not folder_picker_available():
        return None

    initial_dir = _resolve_initial_dir(initial)
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        logger.debug("tkinter unavailable — folder picker disabled")
        return None

    root = tk.Tk()
    root.withdraw()
    root.update_idletasks()
    try:
        root.wm_attributes("-topmost", 1)
    except tk.TclError:
        pass
    try:
        selected = filedialog.askdirectory(
            master=root,
            initialdir=initial_dir or None,
            title=title,
            mustexist=True,
        )
    except tk.TclError as e:
        logger.warning("Folder picker failed: %s", e)
        return None
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass

    if not selected:
        return None
    return str(Path(selected).resolve())


def _resolve_initial_dir(initial: str) -> str:
    raw = initial.strip()
    if not raw:
        return ""
    path = Path(raw).expanduser()
    if path.is_dir():
        return str(path.resolve())
    if path.parent.is_dir():
        return str(path.parent.resolve())
    return ""
