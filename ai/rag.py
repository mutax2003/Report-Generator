"""Lightweight RAG over approved narrative snippets (no external vector DB)."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS_DIR = ROOT / "rag_corpus"


def _tokenize(text: str) -> set[str]:
    return {w.lower() for w in re.findall(r"[a-zA-Z]{3,}", text)}


def load_corpus_from_dir(directory: Path) -> list[tuple[str, str]]:
    """Load RAG chunks from a directory of .txt files."""
    if not directory.is_dir():
        return []
    return list(_cached_corpus_from_dir(str(directory.resolve()), _dir_corpus_mtime(directory)))


def _dir_corpus_mtime(directory: Path) -> int:
    mtimes = [p.stat().st_mtime_ns for p in directory.glob("*.txt") if p.is_file()]
    return max(mtimes) if mtimes else 0


@lru_cache(maxsize=16)
def _cached_corpus_from_dir(dir_str: str, mtime_ns: int) -> tuple[tuple[str, str], ...]:
    directory = Path(dir_str)
    chunks: list[tuple[str, str]] = []
    for path in sorted(directory.glob("*.txt")):
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        prefix = f"{directory.name}/"
        for block in re.split(r"\n---+\n", text):
            block = block.strip()
            if len(block) > 80:
                chunks.append((prefix + path.name, block))
        if not re.search(r"\n---+\n", text) and len(text) > 80:
            key = prefix + path.name
            if (key, text) not in chunks:
                chunks.append((key, text))
    return tuple(chunks)


def clear_rag_cache() -> None:
    """Drop cached project/local RAG chunks (tests)."""
    _cached_corpus_from_dir.cache_clear()


def _load_corpus_chunks() -> list[tuple[str, str]]:
    if not CORPUS_DIR.is_dir():
        return []
    return list(_cached_corpus_from_dir(str(CORPUS_DIR.resolve()), _dir_corpus_mtime(CORPUS_DIR)))


def load_corpus() -> list[tuple[str, str]]:
    """Return (source_name, chunk_text) pairs."""
    return _load_corpus_chunks()


def retrieve(
    query: str,
    *,
    top_k: int = 3,
    extra_dirs: tuple[Path, ...] | None = None,
) -> list[tuple[str, str, float]]:
    """Keyword overlap scoring (offline-friendly)."""
    q_tokens = _tokenize(query)
    if not q_tokens:
        return []
    chunks = load_corpus()
    for d in extra_dirs or ():
        chunks.extend(load_corpus_from_dir(Path(d)))
    scored: list[tuple[str, str, float]] = []
    for source, chunk in chunks:
        c_tokens = _tokenize(chunk)
        if not c_tokens:
            continue
        overlap = len(q_tokens & c_tokens) / max(len(q_tokens), 1)
        if overlap > 0.05:
            scored.append((source, chunk, overlap))
    scored.sort(key=lambda x: -x[2])
    return scored[:top_k]
