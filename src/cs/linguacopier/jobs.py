"""Persistent background copy jobs.

Jobs live in ZODB annotations on the portal, so the feature needs no external
queue or broker. A request enqueues a job through :class:`CopyJobQueue`; a
separate worker (see :mod:`cs.linguacopier.worker`) claims and executes it.
"""

from cs.linguacopier.interfaces import ICopyJob
from cs.linguacopier.interfaces import ICopyJobQueue
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from persistent import Persistent
from persistent.list import PersistentList
from persistent.mapping import PersistentMapping
from plone import api
from zope.annotation.interfaces import IAnnotations
from zope.component import getUtility
from zope.interface import implementer

import uuid

#: Key under which the job store lives in the portal's annotations.
JOB_STORE_KEY = "cs.linguacopier.jobs"

QUEUED = "queued"
RUNNING = "running"
DONE = "done"
FAILED = "failed"
CANCELLED = "cancelled"

#: Upper bound on the per-job error list, so a big job cannot bloat the ZODB.
MAX_ERRORS = 50

#: Used to order finished jobs that (anomalously) have no finish timestamp.
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def now():
    return datetime.now(timezone.utc)


def _iso(value):
    return value.isoformat() if value is not None else None


@implementer(ICopyJob)
class CopyJob(Persistent):
    """A persistent background copy job."""

    def __init__(self, params, requested_by=""):
        self.id = uuid.uuid4().hex
        self.params = PersistentMapping(params)
        self.requested_by = requested_by
        self.created = now()
        self.reset()

    def reset(self):
        """Return the job to a fresh, queued state (used by retry)."""
        self.status = QUEUED
        self.started = None
        self.finished = None
        #: Number of completed work units, kept for resuming a restarted worker.
        self.cursor = None
        self.cancel_requested = False
        self.errors = PersistentList()
        self.last_error = None
        self.progress = PersistentMapping(
            {
                "total": 0,
                "processed": 0,
                "created": 0,
                "updated": 0,
                "skipped": 0,
                "failed": 0,
            }
        )
        self.translation = PersistentMapping(
            {"translated": 0, "partial": 0, "not_translated": 0}
        )

    def add_error(self, source, language, message):
        self.errors.append({"source": source, "language": language, "message": message})
        while len(self.errors) > MAX_ERRORS:
            self.errors.pop(0)
        self.last_error = message

    def to_dict(self):
        return {
            "id": self.id,
            "status": self.status,
            "params": dict(self.params),
            "requested_by": self.requested_by,
            "created": _iso(self.created),
            "started": _iso(self.started),
            "finished": _iso(self.finished),
            "progress": dict(self.progress),
            "translation": dict(self.translation),
            "cancel_requested": self.cancel_requested,
            "errors": [dict(error) for error in self.errors],
        }


class _JobStore(Persistent):
    """The persistent container of jobs plus the worker heartbeat."""

    def __init__(self):
        self.jobs = PersistentMapping()
        self.order = PersistentList()
        self.worker_heartbeat = None


def enqueue_copy(
    context,
    target_languages,
    include_context=False,
    include_children=False,
    translate=False,
    requested_by="",
):
    """Create and queue a background copy job for ``context``."""
    params = {
        "context_path": list(context.getPhysicalPath()),
        "target_languages": list(target_languages),
        "include_context": include_context,
        "include_children": include_children,
        "translate": translate,
    }
    return getUtility(ICopyJobQueue).add(params, requested_by=requested_by)


def get_job_store(portal=None):
    """Return (creating on first use) the portal's job store."""
    if portal is None:
        portal = api.portal.get()
    annotations = IAnnotations(portal)
    store = annotations.get(JOB_STORE_KEY)
    if store is None:
        store = _JobStore()
        annotations[JOB_STORE_KEY] = store
    return store


@implementer(ICopyJobQueue)
class CopyJobQueue:
    """The queue of persistent background copy jobs."""

    def add(self, params, requested_by=""):
        store = get_job_store()
        job = CopyJob(params, requested_by=requested_by)
        store.jobs[job.id] = job
        store.order.append(job.id)
        return job

    def get(self, job_id):
        return get_job_store().jobs.get(job_id)

    def all(self):
        store = get_job_store()
        return [
            store.jobs[job_id]
            for job_id in reversed(store.order)
            if job_id in store.jobs
        ]

    def pending(self):
        # Queued jobs, plus any still marked running — with a single worker a
        # running job means the previous run was interrupted, so it resumes.
        store = get_job_store()
        return [
            store.jobs[job_id]
            for job_id in store.order
            if job_id in store.jobs and store.jobs[job_id].status in (QUEUED, RUNNING)
        ]

    def cancel(self, job_id):
        job = self.get(job_id)
        if job is None:
            return None
        if job.status == QUEUED:
            job.status = CANCELLED
            job.finished = now()
        elif job.status == RUNNING:
            job.cancel_requested = True
        return job

    def retry(self, job_id):
        job = self.get(job_id)
        if job is None or job.status in (QUEUED, RUNNING):
            return job
        job.reset()
        return job

    def delete(self, job_id):
        store = get_job_store()
        job = store.jobs.get(job_id)
        if job is None or job.status == RUNNING:
            return False
        del store.jobs[job_id]
        if job_id in store.order:
            store.order.remove(job_id)
        return True

    def prune(self, retention_days=None, max_jobs=None):
        """Remove finished jobs past the age limit or the maximum count.

        Queued and running jobs are never pruned; of the finished jobs the
        newest ``max_jobs`` are kept. Returns the removed job ids.
        """
        store = get_job_store()
        reference = now()
        removable = []
        finished = []
        for job_id in store.order:
            job = store.jobs.get(job_id)
            if job is None or job.status in (QUEUED, RUNNING):
                continue
            if (
                retention_days is not None
                and job.finished is not None
                and reference - job.finished > timedelta(days=retention_days)
            ):
                removable.append(job_id)
            else:
                finished.append(job_id)
        if max_jobs is not None and len(finished) > max_jobs:
            # Keep the most recently finished; drop the oldest.
            finished.sort(key=lambda job_id: store.jobs[job_id].finished or _EPOCH)
            removable.extend(finished[: len(finished) - max_jobs])
        for job_id in removable:
            if job_id in store.jobs:
                del store.jobs[job_id]
            if job_id in store.order:
                store.order.remove(job_id)
        return removable
