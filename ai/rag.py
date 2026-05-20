"""Lightweight RAG over approved narrative snippets (no external vector DB)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS_DIR = ROOT / "rag_corpus"


def _tokenize(text: str) -> set[str]:
    return {w.lower() for w in re.findall(r"[a-zA-Z]{3,}", text)}


def load_corpus() -> list[tuple[str, str]]:
    """Return (source_name, chunk_text) pairs."""
    chunks: list[tuple[str, str]] = []
    if not CORPUS_DIR.is_dir():
        return chunks
    for path in sorted(CORPUS_DIR.glob("*.txt")):
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        for block in re.split(r"\n---+\n", text):
            block = block.strip()
            if len(block) > 80:
                chunks.append((path.name, block))
        if not re.search(r"\n---+\n", text) and len(text) > 80:
            if (path.name, text) not in chunks:
                chunks.append((path.name, text))
    return chunks


def retrieve(query: str, *, top_k: int = 3) -> list[tuple[str, str, float]]:
    """Keyword overlap scoring (offline-friendly)."""
    q_tokens = _tokenize(query)
    if not q_tokens:
        return []
    scored: list[tuple[str, str, float]] = []
    for source, chunk in load_corpus():
        c_tokens = _tokenize(chunk)
        if not c_tokens:
            continue
        overlap = len(q_tokens & c_tokens) / max(len(q_tokens), 1)
        if overlap > 0.05:
            scored.append((source, chunk, overlap))
    scored.sort(key=lambda x: -x[2])
    return scored[:top_k]
