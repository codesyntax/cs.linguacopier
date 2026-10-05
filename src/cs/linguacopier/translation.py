"""Soft access to plone.app.multilingual's external translation services.

The API (``IExternalTranslationService`` and ``translation_utils.translate_text``)
is unreleased (plone.app.multilingual PR #468). This module guards the import so
that the package works without it, and exposes a single ``translate`` call; the
rest of the package never imports the new API directly.
"""

from logging import getLogger

log = getLogger("cs.linguacopier.translation")

try:
    from plone.app.multilingual.translation_utils import translate_text
except ImportError:  # pragma: no cover - depends on the installed version
    translate_text = None


def translate(value, source_language, target_language):
    """Translate ``value``; return ``None`` when nothing can translate it."""
    if not value or translate_text is None:
        return None
    try:
        return translate_text(value, source_language, target_language) or None
    except Exception:
        log.exception("Translation service failed")
        return None
