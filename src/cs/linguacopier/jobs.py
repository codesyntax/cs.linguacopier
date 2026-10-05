"""Persistent background copy jobs.

Jobs live in ZODB annotations on the portal, so the feature needs no external
queue or broker. A request enqueues a job through :class:`CopyJobQueue`; a
separate worker (see :mod:`cs.linguacopier.worker`) claims and executes it.
"""

from cs.linguacopier.interfaces import ICopyJob
from cs.linguacopier.interfaces import ICopyJobQueue
from datetime import datetime
from datetime import timezone
from persistent import Persistent
from persistent.list import PersistentList
from persistent.mapping import PersistentMapping
from plone import api
from zope.annotation.interfaces import IAnnotations
from zope.interface import implementer

import uuid

#: Key under which the job store lives in the portal's annotations.
JOB_STORE_KEY = "cs.linguacopier.jobs"

QUEUED = "queued"
RUNNING = "running"
DONE = "done"
FAILED = "failed"
CANCELLED = "cancelled"

#: Accepted copy modes: automatic routing, direct (synchronous), background.
MODES = ("auto", "direct", "background")

#: Upper bound on the per-job error list, so a big job cannot bloat the ZODB.
MAX_ERRORS = 50


def now():
    return datetime.now(timezone.utc)


def _iso(value):
    return value.isoformat() if value is not None else None


@implementer(ICopyJob)
class CopyJob(Persistent):
    """A persistent background copy job."""

    def __init__(self, params, requested_by=""):
        self.id = uuid.uuid4().hex
        self.status = QUEUED
        self.params = PersistentMapping(params)
        self.requested_by = requested_by
        self.created = now()
        self.started = None
        self.finished = None
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
        #: Last completed item, kept for resuming a restarted worker.
        self.cursor = None
        self.cancel_requested = False
        self.errors = PersistentList()
        self.last_error = None

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
        store = get_job_store()
        return [
            store.jobs[job_id]
            for job_id in store.order
            if job_id in store.jobs and store.jobs[job_id].status == QUEUED
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
