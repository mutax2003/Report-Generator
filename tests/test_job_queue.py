"""Tests for file-backed render job queue."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import os

from esa_tenant import tenant_subdir
from job_queue import JobStatus, enqueue_render_job, list_pending_jobs, load_job, process_next_job


class JobQueueTests(unittest.TestCase):
    def setUp(self) -> None:
        self._prev = os.environ.get("ESA_TENANT_DATA_ROOT")
        self._tmpdir = tempfile.TemporaryDirectory()
        os.environ["ESA_TENANT_DATA_ROOT"] = self._tmpdir.name

    def tearDown(self) -> None:
        self._tmpdir.cleanup()
        if self._prev is None:
            os.environ.pop("ESA_TENANT_DATA_ROOT", None)
        else:
            os.environ["ESA_TENANT_DATA_ROOT"] = self._prev

    def test_enqueue_and_load(self) -> None:
        job = enqueue_render_job({"excel": "sample.xlsx"}, tenant_id="pilot")
        loaded = load_job(job.job_id, tenant_id="pilot")
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.status, JobStatus.PENDING)

    def test_process_next_job(self) -> None:
        enqueue_render_job({"site": "A"}, tenant_id="pilot")

        def handler(job):
            return tenant_subdir("deliverables", tenant_id=job.tenant_id, create=True) / "out.zip"

        done = process_next_job(handler, tenant_id="pilot")
        self.assertIsNotNone(done)
        assert done is not None
        self.assertEqual(done.status, JobStatus.COMPLETED)
        self.assertEqual(list_pending_jobs(tenant_id="pilot"), [])

    def test_process_next_job_stores_safe_error(self) -> None:
        enqueue_render_job({"site": "B"}, tenant_id="pilot")

        def handler(_job):
            raise PermissionError(r"Access denied: C:\secret\path")

        done = process_next_job(handler, tenant_id="pilot")
        self.assertIsNotNone(done)
        assert done is not None
        self.assertEqual(done.status, JobStatus.FAILED)
        self.assertEqual(done.error, "Permission denied.")
        self.assertNotIn("secret", done.error)

    def test_claim_skips_already_running(self) -> None:
        from job_queue import _claim_pending_job, update_job

        job = enqueue_render_job({"site": "C"}, tenant_id="pilot")
        job.status = JobStatus.RUNNING
        update_job(job)
        claimed = _claim_pending_job("pilot")
        self.assertIsNone(claimed)


if __name__ == "__main__":
    unittest.main()
