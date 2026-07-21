"""
Append-only audit trail with hash-chained entries for regulated deliverables.

Each entry links to the previous entry hash (tamper-evident chain).
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from provenance import sha256_hex

_FALLBACK_AUDIT = ".esa_audit/audit.jsonl"
_APPEND_LOCK = threading.Lock()


def resolve_audit_path(audit_path: Path | None = None) -> Path:
    """Resolve audit log path; reads ESA_AUDIT_LOG at call time (not import time)."""
    if audit_path is not None:
        return audit_path
    return Path(os.environ.get("ESA_AUDIT_LOG", _FALLBACK_AUDIT))


# Back-compat alias — prefer resolve_audit_path() for late env changes.
DEFAULT_AUDIT_PATH = Path(_FALLBACK_AUDIT)


@dataclass
class AuditEntry:
    timestamp: str
    event: str
    actor: str = ""
    tenant_id: str = ""
    resource: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    prev_hash: str = ""
    entry_hash: str = ""

    def canonical_bytes(self) -> bytes:
        payload = asdict(self)
        payload.pop("entry_hash", None)
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def seal(self, prev_hash: str) -> AuditEntry:
        self.prev_hash = prev_hash
        digest = sha256_hex(self.canonical_bytes())
        self.entry_hash = digest
        return self


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _read_last_line(path: Path, *, tail_bytes: int = 65536) -> str:
    """Read the final non-empty line without scanning the whole file."""
    size = path.stat().st_size
    if size == 0:
        return ""
    with path.open("rb") as fh:
        seek_to = max(0, size - tail_bytes)
        fh.seek(seek_to)
        chunk = fh.read()
    # If the tail window did not reach the file start, drop the (likely partial) first line.
    if seek_to > 0:
        newline = chunk.find(b"\n")
        if newline != -1:
            chunk = chunk[newline + 1 :]
    for raw in reversed(chunk.splitlines()):
        stripped = raw.strip()
        if stripped:
            return stripped.decode("utf-8", errors="replace")
    return ""


def _read_last_hash(path: Path) -> str:
    if not path.is_file():
        return ""
    last_line = _read_last_line(path)
    if not last_line:
        return ""
    try:
        row = json.loads(last_line)
    except json.JSONDecodeError:
        return ""
    return str(row.get("entry_hash") or "")


def _platform_lock(fh: Any) -> None:
    if os.name == "nt":
        import msvcrt

        fh.seek(0)
        if fh.read(1) == b"":
            fh.write(b"0")
            fh.flush()
            fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)
    else:
        import fcntl

        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)  # type: ignore[attr-defined]


def _platform_unlock(fh: Any) -> None:
    if os.name == "nt":
        import msvcrt

        fh.seek(0)
        try:
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
    else:
        import fcntl

        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)  # type: ignore[attr-defined]


def append_audit_event(
    event: str,
    *,
    actor: str = "",
    tenant_id: str = "",
    resource: str = "",
    details: dict[str, Any] | None = None,
    audit_path: Path | None = None,
) -> AuditEntry:
    """Append one hash-chained audit entry. Returns the sealed entry."""
    path = resolve_audit_path(audit_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    with _APPEND_LOCK:
        with lock_path.open("a+b") as lock_fh:
            _platform_lock(lock_fh)
            try:
                prev = _read_last_hash(path)
                entry = AuditEntry(
                    timestamp=_utc_now(),
                    event=event,
                    actor=actor,
                    tenant_id=tenant_id,
                    resource=resource,
                    details=dict(details or {}),
                ).seal(prev)
                with path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(asdict(entry), sort_keys=True) + "\n")
                return entry
            finally:
                _platform_unlock(lock_fh)


def verify_audit_chain(audit_path: Path | None = None) -> tuple[bool, str]:
    """Verify hash chain integrity. Returns (ok, message)."""
    path = resolve_audit_path(audit_path)
    if not path.is_file():
        return True, "empty"
    prev = ""
    count = 0
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            count += 1
            row = json.loads(stripped)
            entry = AuditEntry(
                timestamp=row["timestamp"],
                event=row["event"],
                actor=row.get("actor", ""),
                tenant_id=row.get("tenant_id", ""),
                resource=row.get("resource", ""),
                details=row.get("details") or {},
                prev_hash=row.get("prev_hash", ""),
                entry_hash=row.get("entry_hash", ""),
            )
            if entry.prev_hash != prev:
                return False, f"broken chain at line {line_no}"
            expected = sha256_hex(entry.canonical_bytes())
            if entry.entry_hash != expected:
                return False, f"hash mismatch at line {line_no}"
            prev = entry.entry_hash
    return True, f"{count} entries"


def chain_head_hash(audit_path: Path | None = None) -> str:
    return _read_last_hash(resolve_audit_path(audit_path))
