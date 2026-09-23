"""Background jobs that import many skills from one repository.

A collection repository holds hundreds of SKILL.md files; fetching them one
request at a time would block the UI, so the work runs as a tracked job the
frontend polls until it finishes.
"""

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional

from .skill_import import fetch_url
from .skills import save_imported_skill

MAX_CONCURRENCY = 6

_jobs: Dict[str, Dict[str, Any]] = {}


def create_job(entries: List[Dict[str, str]], overwrite: bool = False) -> Dict[str, Any]:
    """Register a bulk import job. Nothing runs until run_job is awaited."""
    if not entries:
        raise ValueError("Select at least one skill to import")

    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {
        "id": job_id,
        "status": "pending",
        "total": len(entries),
        "completed": 0,
        "imported": [],
        "skipped": [],
        "errors": [],
        "overwrite": overwrite,
        "entries": entries,
        "started_at": None,
        "finished_at": None,
    }
    return public_job(_jobs[job_id])


def public_job(job: Dict[str, Any]) -> Dict[str, Any]:
    """Job state without the internal entry list."""
    return {k: v for k, v in job.items() if k != "entries"}


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Current state of a job, or None when the id is unknown."""
    job = _jobs.get(job_id)
    return public_job(job) if job else None


async def _import_entry(job: Dict[str, Any], entry: Dict[str, str], lock: asyncio.Lock) -> None:
    skill_id = entry.get("id", "")
    try:
        content = await fetch_url(entry.get("raw_url", ""))
        if not content or not content.strip():
            raise ValueError("file could not be fetched")
        save_imported_skill(
            skill_id,
            content,
            origin=entry.get("origin"),
            overwrite=job["overwrite"],
        )
        outcome, payload = "imported", skill_id
    except ValueError as e:
        if "already exists" in str(e):
            outcome, payload = "skipped", skill_id
        else:
            outcome, payload = "errors", {"id": skill_id, "error": str(e)}
    except Exception as e:  # network, disk, anything else
        outcome, payload = "errors", {"id": skill_id, "error": str(e)}

    async with lock:
        job[outcome].append(payload)
        job["completed"] += 1


async def run_job(job_id: str) -> Dict[str, Any]:
    """Import every entry of a job, keeping its progress up to date."""
    job = _jobs.get(job_id)
    if not job:
        raise ValueError(f"Unknown import job: {job_id}")

    job["status"] = "running"
    job["started_at"] = time.time()
    lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

    async def guarded(entry):
        async with semaphore:
            await _import_entry(job, entry, lock)

    try:
        await asyncio.gather(*(guarded(entry) for entry in job["entries"]))
        job["status"] = "done"
    except Exception as e:
        job["status"] = "error"
        job["errors"].append({"id": None, "error": str(e)})
    finally:
        job["finished_at"] = time.time()

    return public_job(job)


def start_job(entries: List[Dict[str, str]], overwrite: bool = False) -> Dict[str, Any]:
    """Create a job and run it in the background."""
    job = create_job(entries, overwrite=overwrite)
    asyncio.create_task(run_job(job["id"]))
    return job
