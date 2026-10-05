"""Browser-agnostic content copier.

Copies content (and, optionally, its subobjects) into other languages. Shared by
the classic-UI form and the REST service, so it must not depend on z3c.form or
the browser layer.
"""

from Acquisition import aq_parent
from cs.linguacopier import translation
from cs.linguacopier.fields import is_datagrid_field
from cs.linguacopier.fields import is_translatable_field
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
from Products.CMFCore.interfaces import IFolderish
from z3c.relationfield import RelationValue
from z3c.relationfield.schema import RelationChoice
from z3c.relationfield.schema import RelationList
from zope.component import getAdapters
from zope.component import getUtility
from zope.component import queryUtility
from zope.container.interfaces import INameChooser
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
TRANSLATED = "translated"
PARTIAL = "partial"
NOT_TRANSLATED = "not_translated"


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

        A thin driver over :meth:`items_to_copy` and :meth:`copy_item`, so a
        background job can drive the same steps with its own commit boundaries.
        """
        self.translate = translate
        report = CopyReport()
        items = self.items_to_copy(include_context, include_children)
        for item in items:
            for language in target_languages:
                result = self.copy_item(item, language)
                if isinstance(result, CopyError):
                    report.errors.append(result)
                else:
                    report.successes.append(result)
        if include_children:
            # Once the whole tree is copied, give the target folders the same
            # child order as their source. The context is included even when it
            # was not itself copied: copying only its contents still needs the
            # contents ordered in the context's translation.
            folders = [self.context] + items
            for language in target_languages:
                self._order_targets(folders, language)
        return report

    def child_brains(self):
        """The catalog brains for the context and its descendants, in path order."""
        pcat = api.portal.get_tool("portal_catalog")
        return pcat(path="/".join(self.context.getPhysicalPath()))

    def items_to_copy(self, include_context=False, include_children=False):
        """Return the items a copy would touch, in processing order.

        The addressed object first (when ``include_context``), then its
        descendants sorted by path length (when ``include_children``).
        """
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

    def count_items(self, include_context=False, include_children=False, limit=None):
        """Return how many items a copy would touch, without loading them.

        When ``limit`` is given, counting stops as soon as it is exceeded (the
        result then only means "more than the limit"), so a huge tree is not
        fully walked just to size it.
        """
        count = 0
        if include_context:
            count += 1
            if limit is not None and count > limit:
                return count
        if include_children:
            context_path = "/".join(self.context.getPhysicalPath())
            for brain in self.child_brains():
                if brain.getPath() == context_path:
                    continue
                count += 1
                if limit is not None and count > limit:
                    return count
        return count

    def copy_item(self, item, language):
        """Copy one item into one language; return a ``CopyResult`` or ``CopyError``.

        Best-effort: the item is isolated in its own savepoint, so a failure is
        rolled back and returned without aborting the caller's batch. The copier
        never commits; the caller owns the transaction boundaries. Translation
        follows the copier's ``translate`` setting.
        """
        if item.portal_type in SKIPPED_PORTAL_TYPES:
            log.info("Item skipped: %s", "/".join(item.getPhysicalPath()))
            return CopyResult(target=item, language=language, status=SKIPPED)

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
            return CopyError(source=item, language=language, message=str(e))

        return CopyResult(
            target=translated,
            language=language,
            status=CREATED if created else UPDATED,
            translation=self._translation_outcome(),
        )

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
        # available, so it can be classified and its relations remapped.
        for field_schema in iterSchemata(source):
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
                self.change_content(source_adapter, target_adapter, name, schema_field)

    def change_content(self, source, target, key, field=None):
        source_value = getattr(source, key)
        value = getattr(source_value, "raw", source_value)
        if isinstance(field, RelationList):
            value = self._translated_relations(value, target)
        elif isinstance(field, RelationChoice) and value is not None:
            translated_relation = self._translated_relation(value, target)
            if translated_relation is not None:
                value = translated_relation
        value = self._translated_value(value, field)
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

    def _translated_relations(self, relations, target):
        """Remap a relation list to each related object's translation."""
        if not relations:
            return relations
        translated = []
        for relation in relations:
            new_relation = self._translated_relation(relation, target)
            if new_relation is not None:
                translated.append(new_relation)
        return translated

    def _translated_relation(self, relation, target):
        """The relation to the related object's translation, or ``None``."""
        related = relation.to_object if relation is not None else None
        if related is None:
            return None
        # ``target`` can be a behavior adapter rather than the content object,
        # and such an adapter need not expose ``Language()``. The language the
        # copy is going into is tracked by the copier, so prefer it and only
        # fall back to the object for standalone calls.
        language = self._target_language or target.Language()
        translated = ITranslationManager(related).get_translation(language)
        if translated is None:
            return None
        intids = getUtility(IIntIds)
        try:
            to_id = intids.getId(translated)
        except KeyError:
            to_id = intids.register(translated)
        return RelationValue(to_id)

    def _translated_value(self, value, field):
        """Translate the free-text parts of ``value`` for ``field``.

        Only free text is translated. A data grid recurses into its rows, so the
        same rule handles every cell — and a nested data grid — at any depth.
        """
        if not self.translate or field is None:
            return value
        if is_datagrid_field(field):
            return self._translate_rows(value, field)
        if is_translatable_field(field) and isinstance(value, str) and value:
            return self._translate_text(value)
        return value

    def _translate_text(self, value):
        """Translate free text, counting it for the translation outcome."""
        self._eligible_fields += 1
        translated = self._translate_value(value)
        if translated is None:
            return value
        self._translated_fields += 1
        return translated

    def _translate_rows(self, rows, field):
        """Translate the free-text cells of a data grid's rows."""
        row_schema = getattr(field.value_type, "schema", None)
        if row_schema is None:
            return rows
        translated_rows = []
        for row in rows or []:
            translated_row = dict(row)
            for name, column in getFieldsInOrder(row_schema):
                if name in translated_row:
                    translated_row[name] = self._translated_value(
                        translated_row[name], column
                    )
            translated_rows.append(translated_row)
        return translated_rows

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
