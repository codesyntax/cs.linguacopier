"""Module where all interfaces, events and exceptions live."""

from cs.linguacopier import _
from zope import schema
from zope.interface import Interface
from zope.publisher.interfaces.browser import IDefaultBrowserLayer


class ICsLinguacopierLayer(IDefaultBrowserLayer):
    """Marker interface that defines a browser layer."""


class ILinguacopierSettings(Interface):
    """Registry-backed settings for the content copier."""

    default_mode = schema.Choice(
        title=_("Default copy mode"),
        description=_(
            "How a copy without an explicit mode is run: automatically, "
            "directly, or in the background."
        ),
        vocabulary="cs.linguacopier.CopyModes",
        default="auto",
    )

    direct_max_items = schema.Int(
        title=_("Direct copy size limit"),
        description=_(
            "In automatic mode, run the copy directly when the estimated work "
            "(objects times target languages) is at or below this number."
        ),
        default=20,
    )

    chunk_size = schema.Int(
        title=_("Background chunk size"),
        description=_("Number of items copied between commits in a background job."),
        default=25,
    )

    max_retries = schema.Int(
        title=_("Maximum retries"),
        description=_("How many times a background job retries a transient failure."),
        default=3,
    )

    worker_user = schema.TextLine(
        title=_("Worker user"),
        description=_(
            "User id the background worker runs as. Leave empty to run as the "
            "site owner."
        ),
        default="",
        required=False,
    )

    job_retention_days = schema.Int(
        title=_("Job retention (days)"),
        description=_("Finished jobs older than this are pruned by the worker."),
        default=30,
    )

    max_jobs = schema.Int(
        title=_("Maximum stored jobs"),
        description=_("Finished jobs beyond this many are pruned by the worker."),
        default=200,
    )


class ICopyJob(Interface):
    """A persistent background copy job."""

    def to_dict():
        """Return a JSON-serializable representation of the job."""


class ICopyJobQueue(Interface):
    """The queue of persistent background copy jobs."""

    def add(params, requested_by=""):
        """Create and store a new queued job; return it."""

    def get(job_id):
        """Return the job with ``job_id``, or ``None``."""

    def all():
        """Return every job, newest first."""

    def pending():
        """Return the pending jobs (queued, plus interrupted running ones)."""

    def cancel(job_id):
        """Cancel a job; return it, or ``None`` when it does not exist."""

    def retry(job_id):
        """Re-queue a finished or failed job with the same parameters."""

    def delete(job_id):
        """Remove a job; return whether it existed."""


class ITranslateThings(Interface):
    """This is a multi adapter on (original_item, translated_item)
    to be able to extend the copier with additional features when
    translating."""

    def translate():
        """Method that does something with the original_item and the
        translated_item, probably translating special content-types,
        attributes, annotations, ..."""
