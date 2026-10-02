from z3c.form.interfaces import WidgetActionExecutionError
from zope.interface import Invalid

from cs.linguacopier import _
from cs.linguacopier import languages
from cs.linguacopier.copier import ContentCopier
from cs.linguacopier.copier import CREATED
from cs.linguacopier.copier import SKIPPED
from cs.linguacopier.copier import UPDATED
from logging import getLogger
from plone import api
from plone.app.z3cform.widgets.checkbox import CheckBoxFieldWidget
from plone.autoform import directives
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from z3c.form import button
from z3c.form import field
from z3c.form import form
from zope import schema
from zope.interface import Interface

log = getLogger("cs.linguacopier.copier")

#: Display-only status for an object the copier could not copy.
FAILED = "failed"


def report_counts(report):
    """Return ``{created, updated, skipped, failed}`` counts for a copy report.

    Tolerates ``None`` (no copy ran yet): the form template evaluates the counts
    before its ``tal:condition`` guard, i.e. on the initial GET too.
    """
    counts = {CREATED: 0, UPDATED: 0, SKIPPED: 0, FAILED: 0}
    if report is None:
        return counts
    for result in report.successes:
        counts[result.status] += 1
    counts[FAILED] = len(report.errors)
    return counts


def report_rows(report):
    """Flatten a report into display rows (object, language, status, message)."""
    if report is None:
        return []
    rows = [
        {
            "object": result.target,
            "language": result.language,
            "status": result.status,
            "message": "",
        }
        for result in report.successes
    ]
    rows += [
        {
            "object": error.source,
            "language": error.language,
            "status": FAILED,
            "message": error.message,
        }
        for error in report.errors
    ]
    return rows


class ICopyContentToLanguage(Interface):

    include_context = schema.Bool(
        title=_("Include context element?"),
        description=_("If selected, the context element will be translated"),
        default=True,
        required=False,
    )

    include_children = schema.Bool(
        title=_("Include the contents?"),
        description=_(
            "If selected, all the subobjects of this object will also be translated"
        ),
        default=True,
        required=False,
    )

    target_languages = schema.List(
        title=_("Target languages"),
        description=_("Select into which languages the translation will be made"),
        value_type=schema.Choice(
            title=_("Target languages"),
            vocabulary="cs.linguacopier.AvailableTargetLanguages",
        ),
        required=True,
    )


class CopyContentToLanguage(form.Form):

    fields = field.Fields(ICopyContentToLanguage)
    fields["target_languages"].widgetFactory = CheckBoxFieldWidget

    label = _(
        "Copy the contents of this objects and its subobjects "
        "to the selected language/country"
    )
    ignoreContext = True
    template = ViewPageTemplateFile("copier.pt")

    #: Set by the button handler; the template renders it as the report table.
    report = None

    def updateActions(self, *args, **kwargs):
        super().updateActions(*args, **kwargs)
        self.actions["copy"].klass = self.actions["copy"].klass.replace(
            "btn-secondary", "btn-primary"
        )

    @button.buttonAndHandler(_("Copy content"), name="copy")
    def copy_content_to(self, action):

        data, errors = self.extractData()

        if not data.get("target_languages"):
            msg = _("This field is required")
            raise WidgetActionExecutionError(
                "target_languages",  # Field/widget name
                Invalid(msg),
            )
        if errors:
            self.status = self.formErrorsMessage
            return
        self.report = ContentCopier(self.context).copy(
            data.get("target_languages", []),
            include_context=data.get("include_context", False),
            include_children=data.get("include_children", False),
        )
        log.info("done")
        api.portal.show_message(self._summary_message(), type=self._message_type())
        return

    def _summary_message(self):
        if self.report.errors:
            return _("Some contents could not be copied")
        return _("Contents copied successfully")

    def _message_type(self):
        if not self.report.errors:
            return "info"
        if self.report.successes:
            return "warning"
        return "error"

    @property
    def portal_url(self):
        return api.portal.get().absolute_url()

    @property
    def has_target_languages(self):
        """The template hides the form when there is nothing to copy to."""
        return languages.has_target_languages(self.context)

    @property
    def report_counts(self):
        return report_counts(self.report)

    @property
    def report_rows(self):
        return report_rows(self.report)

    def status_label(self, status):
        return {
            CREATED: _("Created"),
            UPDATED: _("Updated"),
            SKIPPED: _("Skipped"),
            FAILED: _("Failed"),
        }.get(status, status)
