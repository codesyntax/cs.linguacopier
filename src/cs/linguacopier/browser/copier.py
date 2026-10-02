from cs.linguacopier import _
from cs.linguacopier.copier import ContentCopier
from cs.linguacopier.copier import sort_by_physical_path_length
from logging import getLogger
from plone import api
from z3c.form import button
from z3c.form import field
from z3c.form import form
from zope import schema
from zope.interface import Interface


log = getLogger("cs.linguacopier.copier")


class ICopyContentToLanguage(Interface):

    include_context = schema.Bool(
        title=_("Include context element?"),
        description=_("If selected, the context element will be translated"),
        default=False,
    )

    include_children = schema.Bool(
        title=_("Include the contents?"),
        description=_(
            "If selected, all the subobjects of this object " "will also be translated"
        ),
    )

    target_languages = schema.List(
        title=_("Target languages"),
        description=_("Select into which languages " "the translation will be made"),
        value_type=schema.Choice(
            title=_("Target languages"),
            vocabulary="plone.app.vocabularies.SupportedContentLanguages",
        ),
        default=[],
    )


class CopyContentToLanguage(form.Form):

    fields = field.Fields(ICopyContentToLanguage)

    label = _(
        "Copy the contents of this objects and its subobjects "
        "to the selected language/country"
    )
    ignoreContext = True

    @button.buttonAndHandler(_("Copy content"))
    def copy_content_to(self, action):

        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorsMessage
            return
        target_languages = data.get("target_languages", [])
        copier = ContentCopier(self.context)
        if data.get("include_context", False):
            copier.copy_contents_of(self.context, target_languages)

        if data.get("include_children", False):
            pcat = api.portal.get_tool("portal_catalog")
            brains = pcat(path="/".join(self.context.getPhysicalPath()))
            list_of_items = []
            for brain in brains:
                list_of_items.append(brain.getObject())

            list_of_items.sort(key=sort_by_physical_path_length)

            for obj in list_of_items:
                if obj != self.context:
                    copier.copy_contents_of(obj, target_languages)

        log.info("done")
        msg = _("Contents copied successfully")
        api.portal.show_message(msg, type="info")
        return
