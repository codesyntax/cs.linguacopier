"""Which languages a copy can target for a given context.

The single source of truth shared by the form's vocabulary, the form's
"nothing to copy to" guard, and the REST endpoint's validation.
"""

from plone.base.interfaces import ILanguage
from zope.component import getUtility
from zope.schema.interfaces import IVocabularyFactory
from zope.schema.vocabulary import SimpleVocabulary

SUPPORTED_CONTENT_LANGUAGES = "plone.app.vocabularies.SupportedContentLanguages"


def current_language(context):
    """The context's language code, or ``None`` when it has none.

    plone.app.multilingual provides the ``ILanguage`` adapter for Dexterity
    content. A non-Dexterity object fails to adapt (``TypeError``) and a
    language-independent object reports an empty language; both become ``None``.
    """
    if context is None:
        return None
    try:
        return ILanguage(context).get_language() or None
    except TypeError:
        return None


def target_language_vocabulary(context):
    """Supported content languages, minus the context's own language."""
    factory = getUtility(IVocabularyFactory, SUPPORTED_CONTENT_LANGUAGES)
    vocabulary = factory(context)
    current = current_language(context)
    if not current:
        return vocabulary
    return SimpleVocabulary([term for term in vocabulary if term.value != current])


def has_target_languages(context):
    """Whether there is any language other than the context's own to copy to."""
    return len(target_language_vocabulary(context)) > 0
