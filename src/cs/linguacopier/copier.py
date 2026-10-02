"""Browser-agnostic content copier.

Copies content (and, optionally, its subobjects) into other languages. Shared by
the classic-UI form and the REST service, so it must not depend on z3c.form or
the browser layer.
"""

from cs.linguacopier import translation
from cs.linguacopier.interfaces import ITranslateThings
from dataclasses import dataclass
from dataclasses import field
from logging import getLogger
from plone import api
from plone.app.multilingual.interfaces import ITranslationManager
from plone.app.textfield.value import RichTextValue
from plone.behavior.interfaces import IBehaviorAssignable
from plone.dexterity.interfaces import IDexterityContent
from plone.uuid.interfaces import IUUID
from z3c.relationfield import RelationValue
from z3c.relationfield.schema import RelationList
from zope import schema
from zope.component import getAdapters
from zope.component import getUtility
from zope.intid.interfaces import IIntIds
from zope.schema import getFieldsInOrder

import transaction


log = getLogger("cs.linguacopier.copier")

# TODO: Generalize these lists to something editable
SKIPPED_PORTAL_TYPES = ["LIF"]
SKIPPED_FIELDS_DX = ["language", "id"]
CHECKED_PROPERTIES = [
    {"name": "layout", "type": "string"},
    {"name": "default_page", "type": "string"},
]

CREATED = "created"
UPDATED = "updated"
SKIPPED = "skipped"


def sort_by_physical_path_length(x):
    return len(x.getPhysicalPath())


@dataclass
class CopyResult:
    """One successfully copied (or intentionally skipped) object."""

    target: object
    language: str
    status: str


@dataclass
class CopyError:
    """One object that could not be copied, and why."""

    source: object
    language: str
    message: str


@dataclass
class CopyReport:
    """Outcome of a copy: what was copied/skipped and what failed."""

    successes: list[CopyResult] = field(default_factory=list)
    errors: list[CopyError] = field(default_factory=list)


class ContentCopier:
    def __init__(self, context):
        self.context = context
        self.translate = False
        self._source_language = None
        self._target_language = None

    def copy(
        self,
        target_languages,
        include_context=False,
        include_children=False,
        translate=False,
    ):
        """Copy the context and/or its descendants into ``target_languages``.

        Best-effort: each object is isolated in its own savepoint, so a failure
        on one is recorded and rolled back without aborting the rest. The copy
        owns no transaction; the caller (request) commits at the end.

        When ``translate`` is true, text field values are translated with the
        configured external translation service, keeping the original when
        nothing can translate it.
        """
        self.translate = translate
        report = CopyReport()
        for item in self._items_to_copy(include_context, include_children):
            for language in target_languages:
                self._copy_one(item, language, report)
        return report

    def _items_to_copy(self, include_context, include_children):
        items = []
        if include_context:
            items.append(self.context)
        if include_children:
            pcat = api.portal.get_tool("portal_catalog")
            brains = pcat(path="/".join(self.context.getPhysicalPath()))
            descendants = [brain.getObject() for brain in brains]
            descendants = [obj for obj in descendants if obj != self.context]
            descendants.sort(key=sort_by_physical_path_length)
            items.extend(descendants)
        return items

    def _copy_one(self, item, language, report):
        if item.portal_type in SKIPPED_PORTAL_TYPES:
            log.info("Item skipped: %s", "/".join(item.getPhysicalPath()))
            report.successes.append(
                CopyResult(target=item, language=language, status=SKIPPED)
            )
            return

        savepoint = None
        try:
            savepoint = transaction.savepoint()
            manager = ITranslationManager(item)
            created = not manager.has_translation(language)
            if created:
                manager.add_translation(language)
                log.info(
                    "Created translation for %s: %s",
                    "/".join(item.getPhysicalPath()),
                    language,
                )
            translated = manager.get_translation(language)
            self._source_language = item.Language()
            self._target_language = language
            self.copy_fields(item, translated)
            self.copy_other_properties(item, translated)
            self.copy_other_things(item, translated)
            translated.reindexObject()
        except Exception as e:
            if savepoint is not None:
                savepoint.rollback()
            log.exception(e)
            report.errors.append(
                CopyError(source=item, language=language, message=str(e))
            )
            return

        report.successes.append(
            CopyResult(
                target=translated,
                language=language,
                status=CREATED if created else UPDATED,
            )
        )

    def copy_related_fields(self, obj, target_languages):
        # XXX: Where is this used?
        try:
            fields = schema.getFieldsInOrder(obj.getTypeInfo().lookupSchema())
        except AttributeError as e:
            log.info("Error: %s", "/".join(obj.getPhysicalPath()))
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
                            manager = ITranslationManager(element[0].getObject())
                            element_trans = manager.get_translation(language)
                            if element_trans:
                                uid_list.append(IUUID(element_trans))
                    if uid_list:
                        setattr(translated_obj, key, uid_list)
                        translated_obj.reindexObject()

    def copy_other_things(self, original, translated):
        """Use an adapter lookup so developers can extend the copier"""
        adapters = getAdapters((original, translated), ITranslateThings)
        for _name, adapter in adapters:
            adapter.translate()

    def copy_other_properties(self, item, translated):
        # TODO: extract this to an adapter of ITranslateThings
        # TODO: Generalize this list
        for property_item in CHECKED_PROPERTIES:
            property_name = property_item.get("name")
            property_type = property_item.get("type")
            if item.hasProperty(property_name):
                log.info("Copying property %s", property_name)
                if not translated.hasProperty(property_name):
                    translated.manage_addProperty(
                        property_name, item.getProperty(property_name), property_type
                    )
                else:
                    property_dict = {property_name: item.getProperty(property_name)}
                    translated.manage_changeProperties(**property_dict)

    def copy_fields(self, source, target):
        if IDexterityContent.providedBy(source):
            self.copy_fields_dexterity(source, target)

    def copy_fields_dexterity(self, source, target):
        # Copy the content from the canonical fields
        fields = schema.getFieldsInOrder(source.getTypeInfo().lookupSchema())
        for key, value in fields:
            if key.lower() in SKIPPED_FIELDS_DX:
                # skip language
                log.info("Skipped %s", key)
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
                        log.info("Skipped %s", key)
                        continue
                    self.change_content_for_behavior(
                        source, target, key, behavior.interface
                    )

    def change_content(self, source, target, key, field=None):
        source_value = getattr(source, key)
        value = getattr(source_value, "raw", source_value)
        if isinstance(field, RelationList):
            intids = getUtility(IIntIds)
            target_language = target.Language()
            related_translations = []
            for relation_field in value:
                related_element = relation_field.to_object
                if related_element:
                    related_element_translation = ITranslationManager(
                        related_element
                    ).get_translation(target_language)
                    if related_element_translation:
                        try:
                            to_id = intids.getId(related_element_translation)
                        except KeyError:
                            to_id = intids.register(related_element_translation)
                        related_translations.append(RelationValue(to_id))
            value = related_translations
        if self.translate and isinstance(value, str) and value:
            # Scalars and rich text raw HTML are both plain strings here; the
            # original value is kept when the service returns nothing.
            value = self._translate_value(value)
        if getattr(source_value, "raw", None) is not None:
            value = RichTextValue(value, "text/html", "text/x-html-safe")

        setattr(target, key, value)
        if hasattr(source, "getPhysicalPath"):
            log.info("Set attribute %s in %s", key, "/".join(target.getPhysicalPath()))
        else:
            log.info(
                "Set attribute %s in %s",
                key,
                "/".join(target.context.getPhysicalPath()),
            )

    def change_content_for_behavior(self, source, target, key, behavior):
        behaviored_source = behavior(source)
        behaviored_target = behavior(target)
        self.change_content(behaviored_source, behaviored_target, key)

    def _translate_value(self, value):
        """Translate a scalar value, keeping the original when nothing does."""
        translated = translation.translate(
            value, self._source_language, self._target_language
        )
        return translated if translated else value
