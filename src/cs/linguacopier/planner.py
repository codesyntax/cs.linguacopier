"""Decide whether a copy request runs directly or as a background job."""

from cs.linguacopier.copier import ContentCopier
from cs.linguacopier.settings import get_settings

AUTO = "auto"
DIRECT = "direct"
BACKGROUND = "background"

MODES = (AUTO, DIRECT, BACKGROUND)


def plan(
    context,
    mode=None,
    target_languages=(),
    include_context=False,
    include_children=False,
    translate=False,
    settings=None,
):
    """Return ``direct`` or ``background`` for a copy request.

    ``mode`` may be ``None`` to use the configured default. An explicit
    ``direct``/``background`` is honoured; ``auto`` runs directly when there is
    nothing to translate, or when the estimated work (items times target
    languages) fits the configured limit, and in the background otherwise.
    """
    if settings is None:
        settings = get_settings()
    mode = mode or settings.default_mode
    if mode == DIRECT:
        return DIRECT
    if mode == BACKGROUND:
        return BACKGROUND

    if not translate:
        return DIRECT

    threshold = settings.direct_max_items
    count = ContentCopier(context).count_items(
        include_context, include_children, limit=threshold
    )
    if count * len(target_languages) <= threshold:
        return DIRECT
    return BACKGROUND
