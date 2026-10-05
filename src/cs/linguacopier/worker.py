"""Background worker for copy jobs.

Run it as an external command against the same database, scheduled by cron or a
systemd timer, for example::

    bin/instance run src/cs/linguacopier/worker.py

It drains the queued copy jobs oldest-first, copies each with the shared copier
and records progress on the job. It writes a heartbeat so the control panel can
tell whether a worker is running.
"""

from AccessControl.SecurityManagement import getSecurityManager
from AccessControl.SecurityManagement import newSecurityManager
from AccessControl.SecurityManagement import setSecurityManager
from cs.linguacopier.copier import ContentCopier
from cs.linguacopier.interfaces import ICopyJobQueue
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
    """Execute the queued copy jobs, oldest first.

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
    job.status = RUNNING
    job.started = now()
    transaction.commit()

    savepoint = transaction.savepoint()
    try:
        context = _resolve_context(portal, job.params)
        include_context = bool(job.params.get("include_context", False))
        include_children = bool(job.params.get("include_children", False))
        target_languages = list(job.params.get("target_languages", []))
        copier = ContentCopier(context)
        items = copier.items_to_copy(include_context, include_children)
        job.progress["total"] = len(items) * len(target_languages)
        report = copier.copy(
            target_languages,
            include_context=include_context,
            include_children=include_children,
            translate=bool(job.params.get("translate", False)),
        )
    except Exception as e:
        savepoint.rollback()
        failed = getUtility(ICopyJobQueue).get(job.id)
        failed.status = FAILED
        failed.last_error = str(e)
        failed.finished = now()
        transaction.commit()
        log.exception("Copy job %s failed", job.id)
        return

    _record_report(job, report)
    job.status = DONE
    job.finished = now()
    transaction.commit()
    log.info("Copy job %s done: %s", job.id, dict(job.progress))


def _record_report(job, report):
    counts = {"created": 0, "updated": 0, "skipped": 0}
    translation = {"translated": 0, "partial": 0, "not_translated": 0}
    for result in report.successes:
        if result.status in counts:
            counts[result.status] += 1
        if result.translation in translation:
            translation[result.translation] += 1
    job.progress.update(counts)
    job.progress["failed"] = len(report.errors)
    job.progress["processed"] = len(report.successes) + len(report.errors)
    job.progress["total"] = max(job.progress["total"], job.progress["processed"])
    job.translation.update(translation)
    for error in report.errors:
        job.add_error(
            source=_url(error.source),
            language=error.language,
            message=error.message,
        )


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
