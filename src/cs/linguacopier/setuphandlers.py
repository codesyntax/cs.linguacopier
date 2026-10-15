from cs.linguacopier.jobs import get_job_store
from cs.linguacopier.jobs import JOB_STORE_KEY
from plone import api
from plone.base.interfaces import INonInstallable
from zope.annotation.interfaces import IAnnotations
from zope.interface import implementer


@implementer(INonInstallable)
class HiddenProfiles:

    def getNonInstallableProfiles(self):
        """Hide uninstall profile from site-creation and quickinstaller"""
        return [
            "cs.linguacopier:uninstall",
        ]


def post_install(context):
    """Create the persistent store for background copy jobs."""
    get_job_store(api.portal.get())


def uninstall(context):
    """Drop the background copy jobs stored on the portal."""
    annotations = IAnnotations(api.portal.get())
    if JOB_STORE_KEY in annotations:
        del annotations[JOB_STORE_KEY]
