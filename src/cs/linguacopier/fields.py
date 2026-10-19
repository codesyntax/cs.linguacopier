"""Classifying schema fields for translation.

Only free text is worth sending to the translation service; controlled tokens
(vocabulary/taxonomy choices), numbers, booleans, dates and times, e-mail
addresses, URLs, passwords, relations, JSON, and file/image blobs are copied
verbatim. A data grid is not free text either, but its rows are translated
separately (see the copier), so it is called out here.
"""

from plone.app.z3cform.interfaces import ILinkWidget
from plone.autoform.interfaces import IParameterizedWidget
from plone.autoform.interfaces import WIDGETS_KEY
from plone.autoform.utils import resolveDottedName
from plone.supermodel.utils import mergedTaggedValueDict
from z3c.form.interfaces import IWidget
from z3c.relationfield.interfaces import IRelationChoice
from z3c.relationfield.interfaces import IRelationList
from zope.schema.interfaces import IBool
from zope.schema.interfaces import IChoice
from zope.schema.interfaces import IDate
from zope.schema.interfaces import IDatetime
from zope.schema.interfaces import INumber
from zope.schema.interfaces import IPassword
from zope.schema.interfaces import ITime
from zope.schema.interfaces import IURI

import re

try:
    from plone.namedfile.interfaces import INamedField
except ImportError:  # pragma: no cover - optional dependency
    INamedField = None

try:
    from plone.schema import IEmail
except ImportError:  # pragma: no cover - optional dependency
    IEmail = None

try:
    from plone.schema import IJSONField
except ImportError:  # pragma: no cover - optional dependency
    IJSONField = None

try:
    from collective.z3cform.datagridfield.interfaces import IRow as IDataGridRow
except ImportError:  # pragma: no cover - optional dependency
    IDataGridRow = None


#: Field names that carry metadata rather than content, so they are copied
#: verbatim and never translated. These come from the default behaviors — above
#: all the ownership fieldset (creators, contributors, rights) — and would only
#: be sent by mistake because some of them are plain text.
NON_TRANSLATABLE_FIELD_NAMES = frozenset(
    {
        "creators",
        "contributors",
        "rights",
    }
)


#: Field interfaces whose values are never free text worth translating.
NON_TRANSLATABLE_FIELD_INTERFACES = tuple(
    iface
    for iface in (
        IBool,
        IDate,
        IDatetime,
        INumber,
        IPassword,
        ITime,
        IURI,
        IRelationChoice,
        IRelationList,
        INamedField,
        IEmail,
        IJSONField,
    )
    if iface is not None
)

#: Values that start like a URL or e-mail are copied verbatim, not translated.
_URL_PREFIX = re.compile(
    r"^(?:"
    r"[a-z][a-z0-9+.-]*://"
    r"|(?:mailto|tel|sms|news|urn|ftp|ftps|sftp|ssh|git|webcal|data):"
    r"|//"
    r"|/|"
    r"\$\{portal_url\}"
    r"|\$\{navigation_root_url\}"
    r"|www\."
    r")",
    re.IGNORECASE,
)


def is_url(value):
    """Whether a text value is a URL, and so must not be sent to translation."""
    if not isinstance(value, str):
        return False
    value = value.strip()
    if not value:
        return False
    return bool(_URL_PREFIX.match(value))


def _widget_factory(widget):
    if isinstance(widget, str):
        try:
            widget = resolveDottedName(widget)
        except (AttributeError, ImportError, ValueError):
            return None
    if IParameterizedWidget.providedBy(widget):
        widget = widget.widget_factory
        if isinstance(widget, str):
            try:
                widget = resolveDottedName(widget)
            except (AttributeError, ImportError, ValueError):
                return None
    return widget


def is_link_field(field_schema, name):
    """Whether the field uses plone.app.z3cform's LinkWidget."""
    if field_schema is None or name is None:
        return False
    widget = mergedTaggedValueDict(field_schema, WIDGETS_KEY).get(name)
    factory = _widget_factory(widget)
    if factory is None:
        return False
    if IWidget.implementedBy(factory):
        return ILinkWidget.implementedBy(factory)
    return getattr(
        factory, "__module__", ""
    ) == "plone.app.z3cform.widgets.link" and getattr(factory, "__name__", "") in {
        "LinkFieldWidget",
        "LinkWidget",
    }


def is_translatable_field(field):
    """Whether values of ``field`` should be sent to the translation service."""
    if field is None:
        return False
    if getattr(field, "__name__", None) in NON_TRANSLATABLE_FIELD_NAMES:
        return False
    if IChoice.providedBy(field) or IChoice.providedBy(
        getattr(field, "value_type", None)
    ):
        return False
    return not any(
        iface.providedBy(field) for iface in NON_TRANSLATABLE_FIELD_INTERFACES
    )


def is_datagrid_field(field):
    """Whether ``field`` is a data grid — a list of structured rows.

    A data grid is not free text, but the free-text values *inside* its rows are
    worth translating, so it is handled specially rather than skipped.
    """
    if field is None or IDataGridRow is None:
        return False
    return IDataGridRow.providedBy(getattr(field, "value_type", None))
