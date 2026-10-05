from cs.linguacopier import _
from cs.linguacopier.languages import target_language_vocabulary
from cs.linguacopier.planner import AUTO
from cs.linguacopier.planner import BACKGROUND
from cs.linguacopier.planner import DIRECT
from zope.interface import implementer
from zope.schema.interfaces import IVocabularyFactory
from zope.schema.vocabulary import SimpleTerm
from zope.schema.vocabulary import SimpleVocabulary

import collections

#: Display titles for the copy modes, in display order.
MODE_TITLES = collections.OrderedDict(
    [
        (AUTO, _("Automatic")),
        (DIRECT, _("Directly")),
        (BACKGROUND, _("In the background")),
    ]
)


@implementer(IVocabularyFactory)
class AvailableTargetLanguages:
    """Supported content languages a copy can target, minus the context's own."""

    def __call__(self, context):
        return target_language_vocabulary(context)


AvailableTargetLanguagesFactory = AvailableTargetLanguages()


@implementer(IVocabularyFactory)
class CopyModes:
    """The copy modes (automatic, direct, background) with display titles."""

    def __call__(self, context):
        return SimpleVocabulary(
            [SimpleTerm(value, title=title) for value, title in MODE_TITLES.items()]
        )


CopyModesFactory = CopyModes()
