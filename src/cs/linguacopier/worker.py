"""Background worker for copy jobs.

Run it as an external command against the same database, scheduled by cron or a
systemd timer, for example::

    bin/instance run src/cs/linguacopier/worker.py

It drains the queued copy jobs oldest-first, copying each in chunks of a
configured size and committing between them, so a large copy is not one giant
transaction. Progress and a resume cursor are stored on the job, so a worker
restarted mid-job resumes where it stopped, and a job can be cancelled at a
chunk boundary. It writes a heartbeat so the control panel can tell whether a
worker is running.
"""

from AccessControl.SecurityManagement import getSecurityManager
from AccessControl.SecurityManagement import newSecurityManager
from AccessControl.SecurityManagement import setSecurityManager
from cs.linguacopier.copier import ContentCopier
from cs.linguacopier.copier import CopyError
from cs.linguacopier.interfaces import ICopyJobQueue
from cs.linguacopier.jobs import CANCELLED
from cs.linguacopier.jobs import DONE
from cs.linguacopier.jobs import FAILED
from cs.linguacopier.jobs import get_job_store
from cs.linguacopier.jobs import now
from cs.linguacopier.jobs import RUNNING
from cs.linguacopier.settings import get_settings
from logging import getLogger
from plone import api
from zope.component import getUtility
from zope.component.hooks import setSite

import transaction

log = getLogger("cs.linguacopier.worker")


def process_pending_jobs(portal=None, max_jobs=None):
    """Execute the pending copy jobs, oldest first.

    Returns the number of jobs processed.
    """
    if portal is None:
        portal = api.portal.get()
    setSite(portal)
    settings = get_settings()
    _write_heartbeat(portal)

    previous = getSecurityManager()
    try:
        _become_user(portal, settings.worker_user)
        queue = getUtility(ICopyJobQueue)
        processed = 0
        for job in queue.pending():
            if max_jobs is not None and processed >= max_jobs:
                break
            _run_job(portal, job, settings)
            processed += 1
    finally:
        setSecurityManager(previous)
    return processed


def _run_job(portal, job, settings):
    if job.status == CANCELLED:
        return
    job.status = RUNNING
    job.started = now()
    transaction.commit()

    try:
        context = _resolve_context(portal, job.params)
    except Exception as e:
        _mark_failed(job, e)
        return

    copier = ContentCopier(context)
    copier.translate = bool(job.params.get("translate", False))
    units = [
        (item, language)
        for item in copier.items_to_copy(
            bool(job.params.get("include_context", False)),
            bool(job.params.get("include_children", False)),
        )
        for language in job.params.get("target_languages", [])
    ]

    job.progress["total"] = len(units)
    transaction.commit()
    chunk_size = max(1, int(settings.chunk_size))
    max_retries = max(0, int(settings.max_retries))

    index = int(job.cursor or 0)
    while index < len(units):
        if job.cancel_requested:
            _finish(job, CANCELLED)
            log.info("Copy job %s cancelled at %s/%s", job.id, index, len(units))
            return
        chunk = units[index : index + chunk_size]
        job = _run_chunk(job, copier, chunk, index + len(chunk), max_retries)
        if job is None:
            return
        index = job.cursor
        log.info("Copy job %s progress %s/%s", job.id, index, len(units))

    # A cancellation that arrived during the last chunk still counts.
    _finish(job, CANCELLED if job.cancel_requested else DONE)
    log.info("Copy job %s finished: %s", job.id, job.status)


def _run_chunk(job, copier, chunk, new_cursor, max_retries):
    """Copy one chunk and commit it, retrying transient failures.

    Returns the (possibly reloaded) job on success, or ``None`` when the retries
    are exhausted and the job has been marked failed.
    """
    job_id = job.id
    attempts = 0
    while True:
        try:
            for item, language in chunk:
                _record_result(job, copier.copy_item(item, language))
            job.cursor = new_cursor
            transaction.commit()
        except Exception as e:
            transaction.abort()
            attempts += 1
            job = getUtility(ICopyJobQueue).get(job_id)
            if attempts > max_retries:
                _mark_failed(job, e)
                return None
            log.warning("Copy job %s chunk failed, retrying (%s)", job_id, attempts)
            continue
        return job


def _record_result(job, result):
    job.progress["processed"] += 1
    if isinstance(result, CopyError):
        job.progress["failed"] += 1
        job.add_error(
            source=_url(result.source),
            language=result.language,
            message=result.message,
        )
        return
    if result.status in job.progress:
        job.progress[result.status] += 1
    if result.translation in job.translation:
        job.translation[result.translation] += 1


def _mark_failed(job, error):
    job.status = FAILED
    job.last_error = str(error)
    job.finished = now()
    transaction.commit()
    log.error("Copy job %s failed: %s", job.id, error)


def _finish(job, status):
    job.status = status
    job.finished = now()
    transaction.commit()


def _resolve_context(portal, params):
    path = params["context_path"]
    return portal.getPhysicalRoot().unrestrictedTraverse(path)


def _become_user(portal, user_id):
    """Act as the configured user, or the site owner when none is set.

    The worker has no request, so it must pick a user explicitly to hold the
    permission needed to create translations. The site owner has that by
    default.
    """
    if not user_id:
        owner = portal.getOwner()
        if owner is not None:
            newSecurityManager(None, owner.__of__(portal.acl_users))
        return
    acl_users = portal.acl_users
    user = acl_users.getUserById(user_id) or acl_users.getUser(user_id)
    if user is None:
        log.warning("Worker user %r not found; running as the current user", user_id)
        return
    newSecurityManager(None, user.__of__(acl_users))


def _write_heartbeat(portal):
    store = get_job_store(portal)
    store.worker_heartbeat = now()
    transaction.commit()


def _url(obj):
    absolute_url = getattr(obj, "absolute_url", None)
    return absolute_url() if absolute_url is not None else ""


def main(app):
    """Entry point for ``bin/instance run``: process every Plone site's queue."""
    from plone.base.interfaces import IPloneSiteRoot

    sites = [obj for obj in app.objectValues() if IPloneSiteRoot.providedBy(obj)]
    for site in sites:
        process_pending_jobs(site)


if __name__ == "__main__":
    main(app)  # noqa: F821  ``app`` is provided by ``bin/instance run``
