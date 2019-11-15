# -*- coding: utf-8 -*-
from cs.linguacopier import _
from cs.linguacopier.interfaces import ITranslateThings
from logging import getLogger
from plone import api
from plone.app.multilingual.interfaces import ITranslationManager
from plone.app.textfield.value import RichTextValue
from plone.behavior.interfaces import IBehaviorAssignable
from plone.dexterity.interfaces import IDexterityContent
from plone.uuid.interfaces import IUUID
from Products.CMFPlone.utils import safe_unicode
from Products.statusmessages.interfaces import IStatusMessage
from z3c.form import button
from z3c.form import field
from z3c.form import form
from zope import schema
from zope.component import getAdapters
from zope.interface import Interface
from zope.schema import getFieldsInOrder
from zope.intid.interfaces import IIntIds
from z3c.relationfield import RelationValue
from zope.component import getUtility
log = getLogger("cs.linguacopier.copier")
from z3c.relationfield.schema import RelationList


# TODO: Generalize these lists to something editable
SKIPPED_PORTAL_TYPES = ["LIF"]
SKIPPED_FIELDS_AT = ["language"]
SKIPPED_FIELDS_DX = ["language", "id"]
CHECKED_PROPERTIES = [
    {"name": "layout", "type": "string"},
    {"name": "default_page", "type": "string"},
]


def sort_by_physical_path_length(x):
    return len(x.getPhysicalPath())


class ICopyContentToLanguage(Interface):

    context_element = schema.Bool(
        title=_(u"Include context element?"),
        description=_(u"If selected, the context element will be translated"),
        default=False,
    )

    contents_too = schema.Bool(
        title=_(u"Include the contents?"),
        description=_(
            u"If selected, all the subobjects of this object "
            u"will also be translated"
        ),
    )

    target_languages = schema.List(
        title=_(u"Target languages"),
        description=_(u"Select into which languages " u"the translation will be made"),
        value_type=schema.Choice(
            title=_(u"Target languages"),
            vocabulary=u"plone.app.vocabularies.SupportedContentLanguages",
        ),
        default=[],
    )


class CopyContentToLanguage(form.Form):

    fields = field.Fields(ICopyContentToLanguage)

    label = _(
        u"Copy the contents of this objects and its subobjects "
        u"to the selected language/country"
    )
    ignoreContext = True

    @button.buttonAndHandler(_(u"Copy content"))
    def copy_content_to(self, action):

        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorsMessage
            return
        target_languages = data.get("target_languages", [])
        if data.get("context_element", False):
            self.copy_contents_of(self.context, target_languages)

        if data.get("contents_too", False):
            pcat = api.portal.get_tool("portal_catalog")
            brains = pcat(path="/".join(self.context.getPhysicalPath()))
            list_of_items = []
            for brain in brains:
                list_of_items.append(brain.getObject())

            list_of_items.sort(key=sort_by_physical_path_length)

            for obj in list_of_items:
                if obj != self.context:
                    self.copy_contents_of(obj, target_languages)

        log.info("done")
        msg = _(u"Contents copied successfuly")
        IStatusMessage(self.request).add(msg, type="info")
        return

    def copy_related_fields(self, obj, target_languages):
        # XXX: Where is this used?
        try:
            fields = schema.getFieldsInOrder(obj.getTypeInfo().lookupSchema())
        except AttributeError as e:
            log.info("Error: %s" % "/".join(obj.getPhysicalPath()))
            log.exception(e)

        pcat = api.portal.get_tool("portal_catalog")
        for key, value in fields:
            value = value.get(obj)
            if isinstance(value, list):
                manager = ITranslationManager(obj)
                for language in target_languages:
                    translated_obj = manager.get_translation(language)
                    uid_list = []

                    for uid in value:
                        element = pcat(UID=uid, Language=obj.Language())
                        if element:
                            manager = ITranslationManager(
                                element[0].getObject()
                            )  # noqa
                            element_trans = manager.get_translation(language)
                            if element_trans:
                                uid_list.append(IUUID(element_trans))
                    if uid_list:
                        setattr(translated_obj, key, uid_list)
                        translated_obj.reindexObject()

    def copy_contents_of(self, item, target_languages):
        if item.portal_type in SKIPPED_PORTAL_TYPES:
            log.info("Item skipped: {0}".format("/".join(item.getPhysicalPath())))
        else:
            for language in target_languages:
                manager = ITranslationManager(item)
                if not manager.has_translation(language):
                    manager.add_translation(language)
                    log.info(
                        "Created translation for {}: {}".format(
                            "/".join(item.getPhysicalPath()), language
                        )
                    )
                    import transaction

                    transaction.commit()
                translated = manager.get_translation(language)
                self.copy_fields(item, translated)
                self.copy_seo_properties(item, translated)
                self.copy_other_properties(item, translated)
                self.copy_other_things(item, translated)
                # translated.id = safe_unicode(translated.id).encode('utf-8')
                translated.reindexObject()

    def copy_other_things(self, original, translated):
        """ Use an adapter lookup so developers can extend the copier """
        adapters = getAdapters((original, translated), ITranslateThings)
        for adapter in adapters:
            adapter.translate()

    def copy_other_properties(self, item, translated):
        # TODO: extract this to an adapter of ITranslateThings
        # TODO: Generalize this list
        for property_item in CHECKED_PROPERTIES:
            property_name = property_item.get("name")
            property_type = property_item.get("type")
            if item.hasProperty(property_name):
                log.info("Copying property {}".format(property_name))
                if not translated.hasProperty(property_name):
                    translated.manage_addProperty(
                        property_name, item.getProperty(property_name), property_type
                    )
                else:
                    property_dict = dict(property_name=item.getProperty(property_name))
                    translated.manage_changeProperties(**property_dict)

    def copy_fields(self, source, target):
        if IDexterityContent.providedBy(source):
            self.copy_fields_dexterity(source, target)

    def copy_fields_dexterity(self, source, target):
        # Copy the content from the canonical fields
        try:
            fields = schema.getFieldsInOrder(
                source.getTypeInfo().lookupSchema()
            )  # noqa
        except AttributeError as e:
            log.info("Error: %s" % "/".join(source.getPhysicalPath()))
            log.exception(e)
            return
        for key, value in fields:
            if key.lower() in SKIPPED_FIELDS_DX:
                # skip language
                log.info("Skipped %s" % key)
                continue
            self.change_content(source, target, key, value)

        # Copy the contents from behaviors
        behavior_assignable = IBehaviorAssignable(source)
        if behavior_assignable:
            behaviors = behavior_assignable.enumerateBehaviors()
            for behavior in behaviors:
                for key, value in getFieldsInOrder(behavior.interface):
                    if key.lower() in SKIPPED_FIELDS_DX:
                        # skip language
                        log.info("Skipped %s" % key)
                        continue
                    self.change_content_for_behavior(
                        source, target, key, behavior.interface
                    )

    def copy_seo_properties(self, source, target):
        # TODO: extract this to an adapter of ITranslateThings
        # Copy SEO properties added by quintagroup.seoptimizer
        for k, v in source.propertyItems():
            if k.startswith("qSEO_"):
                if target.hasProperty(k):
                    target.manage_changeProperties({k: source.getProperty(k)})
                    path = "/".join(source.getPhysicalPath())
                    log.info("Changed property %s for %s" % (k, path))
                else:
                    if k == "qSEO_keywords":
                        target.manage_addProperty(k, source.getProperty(k), "lines")
                    else:
                        target.manage_addProperty(k, source.getProperty(k), "string")

    def change_content(self, source, target, key, field=None):
        try:
            value = getattr(getattr(source, key), "raw", getattr(source, key))
            if isinstance(field, RelationList):
                intids = getUtility(IIntIds)
                target_language = target.Language()
                related_translations = []
                for relation_field in value:
                    related_element = relation_field.to_object
                    if related_element:
                        related_element_translation = ITranslationManager(related_element).get_translation(target_language)
                        if related_element_translation:
                            try:
                                to_id = intids.getId(related_element_translation)
                            except KeyError:
                                to_id = intids.register(related_element_translation)
                            related_translations.append(RelationValue(to_id))
                value = related_translations
        except Exception as e:
            log.info("Error setting references attribute {} on {}".format(key, target))
            log.exception(e)
        try:
            if getattr(getattr(source, key), "raw", None) is not None:
                value = RichTextValue(value, "text/html", "text/x-html-safe")

            setattr(target, key, value)
            if hasattr(source, "getPhysicalPath"):
                log.info(
                    "Set attribute {} in {}".format(
                        key, "/".join(target.getPhysicalPath())
                    )
                )
            else:
                log.info(
                    "Set attribute {} in {}".format(
                        key, "/".join(target.context.getPhysicalPath())
                    )
                )

        except Exception as e:
            log.info("Error setting attribute {} on {}".format(key, target))
            log.exception(e)

    def change_content_for_behavior(self, source, target, key, behavior):
        behaviored_source = behavior(source)
        behaviored_target = behavior(target)
        self.change_content(behaviored_source, behaviored_target, key)
