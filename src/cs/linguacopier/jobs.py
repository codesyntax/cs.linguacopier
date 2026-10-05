"""Persistent background copy jobs.

Jobs live in ZODB annotations on the portal, so the feature needs no external
queue or broker. A request enqueues a job through :class:`CopyJobQueue`; a
separate worker (see :mod:`cs.linguacopier.worker`) claims and executes it.
"""

from BTrees.IOBTree import IOBTree
from BTrees.OOBTree import OOBTree
from cs.linguacopier.interfaces import ICopyJob
from cs.linguacopier.interfaces import ICopyJobQueue
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from persistent import Persistent
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

#: Upper bound on the errors recorded per job, so a big job cannot bloat the ZODB.
MAX_ERRORS = 50

#: Used to order finished jobs that (anomalously) have no finish timestamp.
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def now():
    return datetime.now(timezone.utc)


def _iso(value):
    return value.isoformat() if value is not None else None


@implementer(ICopyJob)
class CopyJob(Persistent):
    """A persistent background copy job.

    Its collections are BTrees rather than the monolithic persistent mapping and
    list types: a mutation rewrites only the affected BTree buckets, so a job
    does not re-serialise a whole structure into the Data.fs on every change.
    """

    def __init__(self, params, requested_by=""):
        self.id = uuid.uuid4().hex
        #: Position in the store's order tree; set when the job is queued.
        self.sequence = None
        self.params = OOBTree(params)
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
        self.errors = IOBTree()
        self.last_error = None
        self.progress = OOBTree(
            {
                "total": 0,
                "processed": 0,
                "created": 0,
                "updated": 0,
                "skipped": 0,
                "failed": 0,
            }
        )
        self.translation = OOBTree({"translated": 0, "partial": 0, "not_translated": 0})

    def add_error(self, source, language, message):
        key = self.errors.maxKey() + 1 if self.errors else 0
        self.errors[key] = {"source": source, "language": language, "message": message}
        while len(self.errors) > MAX_ERRORS:
            del self.errors[self.errors.minKey()]
        self.last_error = message

    def recent_errors(self):
        """The recorded errors, oldest first."""
        return [dict(error) for error in self.errors.values()]

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
            "errors": self.recent_errors(),
        }


class _JobStore(Persistent):
    """The persistent container of jobs plus the worker heartbeat.

    Both trees are BTrees, so adding, deleting or pruning a job rewrites a few
    buckets rather than re-serialising the whole collection.
    """

    def __init__(self):
        #: job id -> CopyJob
        self.jobs = OOBTree()
        #: monotonically increasing sequence -> job id (keeps insertion order)
        self.order = IOBTree()
        self._next_sequence = 0
        self.worker_heartbeat = None

    def add(self, job):
        """Store ``job`` at the next sequence, so it stays in insertion order."""
        job.sequence = self._next_sequence
        self._next_sequence += 1
        self.jobs[job.id] = job
        self.order[job.sequence] = job.id

    def remove(self, job_id):
        """Remove a job and its order entry (the sequence/order stay in step)."""
        job = self.jobs.get(job_id)
        if job is None:
            return
        del self.jobs[job_id]
        if job.sequence is not None and job.sequence in self.order:
            del self.order[job.sequence]

    def job_for(self, seq):
        """Return the job stored at sequence ``seq``, or ``None``."""
        job_id = self.order.get(seq)
        return self.jobs.get(job_id) if job_id is not None else None


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
        store.add(job)
        return job

    def get(self, job_id):
        return get_job_store().jobs.get(job_id)

    def all(self):
        store = get_job_store()
        # The order tree iterates oldest-first; reverse it for newest-first.
        job_ids = list(store.order.values())
        job_ids.reverse()
        return [
            job
            for job in (store.jobs.get(job_id) for job_id in job_ids)
            if job is not None
        ]

    def pending(self):
        # Queued jobs, plus any still marked running — with a single worker a
        # running job means the previous run was interrupted, so it resumes.
        store = get_job_store()
        result = []
        for seq in store.order.keys():
            job = store.job_for(seq)
            if job is not None and job.status in (QUEUED, RUNNING):
                result.append(job)
        return result

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
        store.remove(job_id)
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
        for seq in store.order.keys():
            job = store.job_for(seq)
            if job is None or job.status in (QUEUED, RUNNING):
                continue
            if (
                retention_days is not None
                and job.finished is not None
                and reference - job.finished > timedelta(days=retention_days)
            ):
                removable.append(seq)
            else:
                finished.append(seq)
        if max_jobs is not None and len(finished) > max_jobs:
            # Keep the most recently finished; drop the oldest.
            finished.sort(key=lambda seq: store.job_for(seq).finished or _EPOCH)
            removable.extend(finished[: len(finished) - max_jobs])
        removed_ids = []
        for seq in removable:
            job_id = store.order.get(seq)
            if job_id is None:
                continue
            store.remove(job_id)
            removed_ids.append(job_id)
        return removed_ids
