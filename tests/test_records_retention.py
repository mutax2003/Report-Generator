"""Tests for records retention policy."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from records_retention import RetentionPolicy, files_exceeding_retention, load_retention_policy, purge_stale_files


class RecordsRetentionTests(unittest.TestCase):
    def test_default_policy_loads(self) -> None:
        policy = load_retention_policy()
        self.assertGreaterEqual(policy.deliverable_days, 365)

    def test_purge_dry_run_lists_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / "old_report.docx"
            old.write_bytes(b"docx")
            old_time = datetime.now(timezone.utc) - timedelta(days=4000)
            ts = old_time.timestamp()
            import os

            os.utime(old, (ts, ts))
            stale = purge_stale_files(root, max_age_days=2555, dry_run=True)
            self.assertIn(old, stale)
            self.assertTrue(old.is_file())

    def test_policy_from_dict(self) -> None:
        policy = RetentionPolicy.from_dict({"deliverable_days": 90})
        self.assertEqual(policy.deliverable_days, 90)

    def test_files_exceeding_retention_empty_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(files_exceeding_retention(Path(tmp), max_age_days=30), [])

    def test_policy_path_reads_env_at_call_time(self) -> None:
        import json
        import os

        from records_retention import resolve_policy_path

        with tempfile.TemporaryDirectory() as tmp:
            policy_file = Path(tmp) / "policy.json"
            policy_file.write_text(
                json.dumps({"deliverable_days": 42, "audit_log_days": 42, "temp_upload_days": 7}),
                encoding="utf-8",
            )
            prev = os.environ.get("ESA_RETENTION_POLICY")
            try:
                os.environ["ESA_RETENTION_POLICY"] = str(policy_file)
                policy = load_retention_policy()
                self.assertEqual(policy.deliverable_days, 42)
                self.assertEqual(resolve_policy_path(), policy_file)
            finally:
                if prev is None:
                    os.environ.pop("ESA_RETENTION_POLICY", None)
                else:
                    os.environ["ESA_RETENTION_POLICY"] = prev


if __name__ == "__main__":
    unittest.main()
