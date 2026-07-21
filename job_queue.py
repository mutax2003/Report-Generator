"""
Simple file-backed job queue for batch render workloads (SaaS / async path).
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from esa_tenant import tenant_subdir


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class RenderJob:
    job_id: str
    tenant_id: str
    status: JobStatus
    created_at: str
    updated_at: str
    payload: dict[str, Any] = field(default_factory=dict)
    result_path: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RenderJob:
        return cls(
            job_id=str(data["job_id"]),
            tenant_id=str(data.get("tenant_id", "default")),
            status=JobStatus(str(data.get("status", JobStatus.PENDING.value))),
            created_at=str(data["created_at"]),
            updated_at=str(data.get("updated_at", data["created_at"])),
            payload=dict(data.get("payload") or {}),
            result_path=str(data.get("result_path", "")),
            error=str(data.get("error", "")),
        )


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _queue_dir(tenant_id: str = "default") -> Path:
    return tenant_subdir("jobs", tenant_id=tenant_id, create=True)


def enqueue_render_job(payload: dict[str, Any], *, tenant_id: str = "default") -> RenderJob:
    job_id = uuid.uuid4().hex
    now = _utc_now()
    job = RenderJob(
        job_id=job_id,
        tenant_id=tenant_id,
        status=JobStatus.PENDING,
        created_at=now,
        updated_at=now,
        payload=payload,
    )
    path = _queue_dir(tenant_id) / f"{job_id}.json"
    path.write_text(json.dumps(job.to_dict(), indent=2), encoding="utf-8")
    return job


def load_job(job_id: str, *, tenant_id: str = "default") -> RenderJob | None:
    path = _queue_dir(tenant_id) / f"{job_id}.json"
    if not path.is_file():
        return None
    return RenderJob.from_dict(json.loads(path.read_text(encoding="utf-8")))


def update_job(job: RenderJob) -> None:
    job.updated_at = _utc_now()
    path = _queue_dir(job.tenant_id) / f"{job.job_id}.json"
    path.write_text(json.dumps(job.to_dict(), indent=2), encoding="utf-8")


def list_pending_jobs(*, tenant_id: str = "default", limit: int = 50) -> list[RenderJob]:
    jobs: list[RenderJob] = []
    for path in sorted(_queue_dir(tenant_id).glob("*.json")):
        job = RenderJob.from_dict(json.loads(path.read_text(encoding="utf-8")))
        if job.status == JobStatus.PENDING:
            jobs.append(job)
        if len(jobs) >= limit:
            break
    return jobs


def _claim_pending_job(tenant_id: str) -> RenderJob | None:
    """Atomically claim one pending job via exclusive lock file."""
    for path in sorted(_queue_dir(tenant_id).glob("*.json")):
        lock_path = path.with_suffix(".lock")
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            continue
        try:
            if not path.is_file():
                continue
            job = RenderJob.from_dict(json.loads(path.read_text(encoding="utf-8")))
            if job.status != JobStatus.PENDING:
                continue
            job.status = JobStatus.RUNNING
            update_job(job)
            return job
        finally:
            try:
                os.close(fd)
            except OSError:
                pass
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                pass
    return None


def process_next_job(
    handler: Any,
    *,
    tenant_id: str = "default",
) -> RenderJob | None:
    """Claim one pending job, invoke handler(job), persist result."""
    job = _claim_pending_job(tenant_id=tenant_id)
    if job is None:
        return None
    try:
        result_path = handler(job)
        job.status = JobStatus.COMPLETED
        job.result_path = str(result_path or "")
        job.error = ""
    except Exception as exc:  # noqa: BLE001 — job runner captures failure
        from security import user_safe_error

        job.status = JobStatus.FAILED
        job.error = user_safe_error(exc)
    update_job(job)
    return job
