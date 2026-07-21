"""Tests for append-only audit trail."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from audit_trail import append_audit_event, resolve_audit_path, verify_audit_chain


class AuditTrailTests(unittest.TestCase):
    def test_hash_chain_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            append_audit_event("render.start", actor="tester", audit_path=path, details={"site": "A"})
            append_audit_event("render.complete", actor="tester", audit_path=path, details={"ok": True})
            ok, msg = verify_audit_chain(path)
            self.assertTrue(ok, msg)
            self.assertIn("2 entries", msg)

    def test_tail_read_finds_last_hash_many_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            last = None
            for i in range(50):
                last = append_audit_event("render", audit_path=path, details={"n": i})
            from audit_trail import chain_head_hash

            assert last is not None
            self.assertEqual(chain_head_hash(path), last.entry_hash)
            ok, msg = verify_audit_chain(path)
            self.assertTrue(ok, msg)

    def test_tamper_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            append_audit_event("render.start", audit_path=path)
            row = json.loads(path.read_text(encoding="utf-8").strip())
            row["entry_hash"] = "0" * 64
            path.write_text(json.dumps(row) + "\n", encoding="utf-8")
            ok, msg = verify_audit_chain(path)
            self.assertFalse(ok)
            self.assertIn("hash mismatch", msg)

    def test_audit_path_reads_env_at_call_time(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "late.jsonl"
            prev = os.environ.get("ESA_AUDIT_LOG")
            try:
                os.environ["ESA_AUDIT_LOG"] = str(target)
                append_audit_event("render.start", actor="late")
                self.assertTrue(target.is_file())
                self.assertEqual(resolve_audit_path(), target)
            finally:
                if prev is None:
                    os.environ.pop("ESA_AUDIT_LOG", None)
                else:
                    os.environ["ESA_AUDIT_LOG"] = prev
                if target.is_file():
                    target.unlink()
                lock = target.with_name(target.name + ".lock")
                if lock.is_file():
                    lock.unlink()


if __name__ == "__main__":
    unittest.main()
