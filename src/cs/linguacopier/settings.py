"""Access to the copier's registry-backed settings."""

from cs.linguacopier.interfaces import ILinguacopierSettings
from plone.registry.interfaces import IRegistry
from zope.component import getUtility


def get_settings():
    """Return the copier settings (tolerating records missing on old sites)."""
    registry = getUtility(IRegistry)
    return registry.forInterface(
        ILinguacopierSettings, prefix="cs.linguacopier", check=False
    )
