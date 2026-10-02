from cs.linguacopier.languages import target_language_vocabulary
from zope.interface import implementer
from zope.schema.interfaces import IVocabularyFactory


@implementer(IVocabularyFactory)
class AvailableTargetLanguages:
    """Supported content languages a copy can target, minus the context's own."""

    def __call__(self, context):
        return target_language_vocabulary(context)


AvailableTargetLanguagesFactory = AvailableTargetLanguages()
