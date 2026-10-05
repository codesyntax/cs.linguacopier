"""Site Setup control panels for the content copier.

Two configlets: a settings form backed by the registry, and a read-and-manage
view of the background copy jobs.
"""

from cs.linguacopier import _
from cs.linguacopier.interfaces import ICopyJobQueue
from cs.linguacopier.interfaces import ILinguacopierSettings
from cs.linguacopier.jobs import CANCELLED
from cs.linguacopier.jobs import DONE
from cs.linguacopier.jobs import FAILED
from cs.linguacopier.jobs import get_job_store
from cs.linguacopier.jobs import QUEUED
from cs.linguacopier.jobs import RUNNING
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from plone.app.registry.browser.controlpanel import ControlPanelFormWrapper
from plone.app.registry.browser.controlpanel import RegistryEditForm
from plone.z3cform import layout
from Products.Five.browser import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.statusmessages.interfaces import IStatusMessage
from zope.component import getUtility

#: How long without a heartbeat before the worker is considered stalled.
HEARTBEAT_MAX_AGE = timedelta(minutes=10)


class LinguacopierSettingsForm(RegistryEditForm):
    schema = ILinguacopierSettings
    schema_prefix = "cs.linguacopier"
    label = _("Content copier")
    description = _("Configure the content copier and how its background jobs are run.")


LinguacopierSettingsView = layout.wrap_form(
    LinguacopierSettingsForm, ControlPanelFormWrapper
)


class JobsView(BrowserView):
    index = ViewPageTemplateFile("jobs.pt")

    def __call__(self):
        self.update()
        return self.index()

    def update(self):
        # Actions are state-changing, so only accept them over POST (which
        # plone.protect guards with the authenticator token).
        if self.request.method == "POST":
            action = self.request.form.get("action")
            job_id = self.request.form.get("job_id")
            if action and job_id:
                self._act(action, job_id)
        # Keep refreshing while work is in progress, but stop once the worker
        # has gone quiet, so a stalled queue does not reload forever.
        if not self.heartbeat_is_stale and any(
            job.status in (QUEUED, RUNNING) for job in self.jobs
        ):
            self.request.response.setHeader("Refresh", "10")

    def _act(self, action, job_id):
        queue = getUtility(ICopyJobQueue)
        messages = IStatusMessage(self.request)
        if action == "cancel":
            if queue.cancel(job_id) is None:
                messages.addStatusMessage(_("No such job."), "error")
            else:
                messages.addStatusMessage(_("Job cancelled."), "info")
        elif action == "retry":
            job = queue.retry(job_id)
            if job is None:
                messages.addStatusMessage(_("No such job."), "error")
            elif job.status == QUEUED:
                messages.addStatusMessage(_("Job queued again."), "info")
            else:
                messages.addStatusMessage(_("The job cannot be retried."), "warning")
        elif action == "delete":
            if queue.delete(job_id):
                messages.addStatusMessage(_("Job deleted."), "info")
            else:
                messages.addStatusMessage(_("The job cannot be deleted."), "error")

    @property
    def jobs(self):
        return getUtility(ICopyJobQueue).all()

    @property
    def csrf_token(self):
        return self.context.restrictedTraverse("@@authenticator").token()

    @property
    def heartbeat(self):
        return get_job_store(self.context).worker_heartbeat

    @property
    def heartbeat_is_stale(self):
        heartbeat = self.heartbeat
        if heartbeat is None:
            return True
        return datetime.now(timezone.utc) - heartbeat > HEARTBEAT_MAX_AGE

    @staticmethod
    def format_time(value):
        return value.strftime("%Y-%m-%d %H:%M") if value else ""

    def status_label(self, status):
        return {
            QUEUED: _("Queued"),
            RUNNING: _("Running"),
            DONE: _("Done"),
            FAILED: _("Failed"),
            CANCELLED: _("Cancelled"),
        }.get(status, status)

    def progress_percent(self, job):
        total = job.progress.get("total", 0)
        if not total:
            return 0
        return int(round(job.progress.get("processed", 0) * 100 / total))
