"""Browser-agnostic content copier.

Copies content (and, optionally, its subobjects) into other languages. Shared by
the classic-UI form and the REST service, so it must not depend on z3c.form or
the browser layer.
"""

from Acquisition import aq_parent
from cs.linguacopier import translation
from cs.linguacopier.interfaces import ITranslateThings
from dataclasses import dataclass
from dataclasses import field
from logging import getLogger
from plone import api
from plone.app.multilingual.dx.interfaces import ILanguageIndependentField
from plone.app.multilingual.interfaces import ITranslationManager
from plone.app.textfield.value import RichTextValue
from plone.dexterity.interfaces import IDexterityContent
from plone.dexterity.utils import iterSchemata
from plone.folder.interfaces import IExplicitOrdering
from plone.i18n.normalizer.interfaces import IURLNormalizer
from plone.uuid.interfaces import IUUID
from Products.CMFCore.interfaces import IFolderish
from z3c.relationfield import RelationValue
from z3c.relationfield.schema import RelationList
from zope import schema
from zope.component import getAdapters
from zope.component import getUtility
from zope.component import queryUtility
from zope.container.interfaces import INameChooser
from zope.intid.interfaces import IIntIds
from zope.schema import getFieldsInOrder
from zope.schema.interfaces import IChoice

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
TRANSLATED = "translated"
PARTIAL = "partial"
NOT_TRANSLATED = "not_translated"


def is_token_valued(field):
    """Whether a schema field stores a controlled token, not free text.

    A ``Choice`` field, or a collection whose ``value_type`` is a ``Choice``,
    holds a vocabulary/taxonomy token; translating it would store an invalid
    value that can break rendering. This is the same test ``plone.restapi`` uses
    to recognise enumerable fields.
    """
    if IChoice.providedBy(field):
        return True
    value_type = getattr(field, "value_type", None)
    return value_type is not None and IChoice.providedBy(value_type)


def derive_id_from_title(obj, language):
    """Rename ``obj`` to an id derived from its title, in ``language``.

    Plone's normalizing name chooser derives an id from a title, but from the
    request's (or the generic) normalizer. Here the title is normalized with the
    **target language's** normalizer, so the URL reads correctly in that language
    whether or not there is a request (the background worker has none). Plone's
    name chooser is then reused for uniqueness. Does nothing when the title is
    empty or normalizes to nothing, so the object keeps its default id.
    """
    title = getattr(obj, "title", "") or ""
    if not title:
        return
    # The target language's normalizer transliterates (e.g. "ä" -> "ae"); the
    # generic normalizer then slugifies to a URL-safe id. This is done here, not
    # left to the name chooser, which would use the *request's* normalizer (or
    # the generic one) and so ignore the target language.
    language_normalizer = queryUtility(IURLNormalizer, name=language)
    if language_normalizer is not None:
        title = language_normalizer.normalize(title)
    normalized = getUtility(IURLNormalizer).normalize(title)
    # Nothing to do when the title normalizes to nothing, or when the derived id
    # is already the object's id. (The name chooser treats the object itself as a
    # collision, so calling it with the current id would wrongly append "-1".)
    if not normalized or normalized == obj.getId():
        return
    parent = aq_parent(obj)
    new_id = INameChooser(parent).chooseName(normalized, obj)
    if new_id != obj.getId():
        parent.manage_renameObject(obj.getId(), new_id)


@dataclass
class CopyResult:
    """One successfully copied (or intentionally skipped) object."""

    target: object
    language: str
    status: str
    #: Translation outcome when translation was requested; None otherwise.
    translation: str = None


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
        self._eligible_fields = 0
        self._translated_fields = 0

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
        items = self._items_to_copy(include_context, include_children)
        for item in items:
            for language in target_languages:
                self._copy_one(item, language, report)
        if include_children:
            # Once the whole tree is copied, give the target folders the same
            # child order as their source. The context is included even when it
            # was not itself copied: copying only its contents still needs the
            # contents ordered in the context's translation.
            folders = [self.context] + items
            for language in target_languages:
                self._order_targets(folders, language)
        return report

    def _items_to_copy(self, include_context, include_children):
        items = []
        if include_context:
            items.append(self.context)
        if include_children:
            items.extend(self._descendants_in_order(self.context))
        return items

    def _descendants_in_order(self, folder):
        """The descendants of ``folder``, depth first in document order.

        Each folder's direct children are read from the catalog ordered by their
        position in the parent — ``depth`` inside the path query keeps the result
        to the direct children. Recursing gives the whole subtree in the source's
        sibling order, and keeps the catalog's filtering.
        """
        pcat = api.portal.get_tool("portal_catalog")
        folder_path = "/".join(folder.getPhysicalPath())
        brains = pcat(
            {
                "path": {"query": folder_path, "depth": 1},
                "sort_on": "getObjPositionInParent",
            }
        )
        ordered = []
        for brain in brains:
            child = brain.getObject()
            ordered.append(child)
            if IFolderish.providedBy(child):
                ordered.extend(self._descendants_in_order(child))
        return ordered

    def _order_targets(self, folders, language):
        """Set each target folder's order to match its source's, best effort."""
        for item in folders:
            if not IFolderish.providedBy(item):
                continue
            target = ITranslationManager(item).get_translation(language)
            if target is None:
                continue
            savepoint = transaction.savepoint()
            try:
                ordered_ids = []
                for child in item.objectValues():
                    child_target = ITranslationManager(child).get_translation(language)
                    if child_target is not None:
                        ordered_ids.append(child_target.getId())
                self._apply_order(target, ordered_ids)
            except Exception:
                savepoint.rollback()
                log.exception(
                    "Could not order the translation of %s",
                    "/".join(item.getPhysicalPath()),
                )

    def _apply_order(self, folder, ordered_ids):
        if not ordered_ids:
            return
        ordering = folder.getOrdering()
        if not IExplicitOrdering.providedBy(ordering):
            return
        current_ids = set(folder.objectIds())
        for index, obj_id in enumerate(ordered_ids):
            if obj_id in current_ids:
                ordering.moveObjectToPosition(obj_id, index)

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
            self._eligible_fields = 0
            self._translated_fields = 0
            self.copy_fields(item, translated)
            if created and self.translate:
                # The translated title is now in place; give the copy an id in
                # the target language. Only on creation, so re-copies keep it.
                derive_id_from_title(translated, language)
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
                translation=self._translation_outcome(),
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
        # iterSchemata yields the object's own schema first, then a schema per
        # enabled behavior. Each field is seen once and its field object is
        # available, which the language-independent check needs.
        for index, field_schema in enumerate(iterSchemata(source)):
            source_adapter = field_schema(source, None)
            target_adapter = field_schema(target, None)
            if source_adapter is None or target_adapter is None:
                continue
            for name, schema_field in getFieldsInOrder(field_schema):
                if name.lower() in SKIPPED_FIELDS_DX:
                    # skip language
                    log.info("Skipped %s", name)
                    continue
                if ILanguageIndependentField.providedBy(schema_field):
                    # Language-independent fields are shared across
                    # translations: plone.app.multilingual copies them (remapping
                    # relations) when a translation is created and keeps them in
                    # sync afterwards, so the copier leaves them alone.
                    continue
                self.change_content(
                    source_adapter,
                    target_adapter,
                    name,
                    None if index else schema_field,
                    # Vocabulary/taxonomy/choice fields hold tokens, not free
                    # text; copy them verbatim so the copy never stores an
                    # invalid value.
                    translatable=not is_token_valued(schema_field),
                )

    def change_content(self, source, target, key, field=None, translatable=True):
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
        if self.translate and translatable and isinstance(value, str) and value:
            # Scalars and rich text raw HTML are both plain strings here; the
            # original value is kept when the service returns nothing.
            self._eligible_fields += 1
            translated_value = self._translate_value(value)
            if translated_value is not None:
                self._translated_fields += 1
                value = translated_value
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

    def _translate_value(self, value):
        """Translate a value; return ``None`` when nothing translated it."""
        return translation.translate(
            value, self._source_language, self._target_language
        )

    def _translation_outcome(self):
        """Three-valued outcome of translating one copied object."""
        if not self.translate:
            return None
        if not self._eligible_fields or not self._translated_fields:
            return NOT_TRANSLATED
        if self._translated_fields == self._eligible_fields:
            return TRANSLATED
        return PARTIAL
