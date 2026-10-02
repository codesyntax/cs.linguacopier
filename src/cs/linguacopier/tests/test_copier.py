"""Tests for the content copier."""

from cs.linguacopier.browser.copier import CopyContentToLanguage
from cs.linguacopier.browser.copier import ICopyContentToLanguage
from cs.linguacopier.copier import ContentCopier
from cs.linguacopier.copier import sort_by_physical_path_length
from cs.linguacopier.interfaces import ITranslateThings
from cs.linguacopier.testing import CS_LINGUACOPIER_FUNCTIONAL_TESTING
from plone.app.multilingual.interfaces import ITranslationManager
from plone.app.relationfield.behavior import IRelatedItems
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.app.textfield.value import RichTextValue
from plone.dexterity.interfaces import IDexterityContent
from plone.dexterity.utils import createContentInContainer
from Products.statusmessages.interfaces import IStatusMessage
from z3c.relationfield import RelationValue
from zope.component import getGlobalSiteManager
from zope.component import getUtility
from zope.intid.interfaces import IIntIds

import unittest


class DummyContent:
    def __init__(self, path):
        self._path = path

    def getPhysicalPath(self):
        return self._path


class TestHelpers(unittest.TestCase):
    def test_sort_by_physical_path_length(self):
        a = DummyContent(("plone", "ca", "a"))
        b = DummyContent(("plone", "ca", "a", "b", "c"))
        c = DummyContent(("plone", "ca", "a", "b"))
        self.assertEqual(sort_by_physical_path_length(a), 3)

        result = sorted([b, c, a], key=sort_by_physical_path_length)
        self.assertEqual(result, [a, c, b])

    def test_interface_defaults(self):
        self.assertFalse(ICopyContentToLanguage["include_context"].default)
        self.assertEqual(ICopyContentToLanguage["target_languages"].default, [])


class TestCopier(unittest.TestCase):
    layer = CS_LINGUACOPIER_FUNCTIONAL_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        self.ca = self.portal["ca"]

    def _create_document(self, container=None, title="A document", text=None):
        container = container if container is not None else self.ca
        kwargs = {}
        if text is not None:
            kwargs["text"] = RichTextValue(text, "text/html", "text/x-html-safe")
        return createContentInContainer(container, "Document", title=title, **kwargs)

    def _form_for(self, obj):
        return CopyContentToLanguage(obj, self.request)

    def _copy_contents_of(self, obj, languages):
        ContentCopier(obj).copy_contents_of(obj, languages)

    def _run_handler(self, obj, data, errors=None):
        form = self._form_for(obj)
        form.extractData = lambda: (data, errors or [])
        form.copy_content_to(form, None)
        return form

    # copy_contents_of / copy pipeline

    def test_copy_contents_of_creates_translation(self):
        doc = self._create_document(title="Hello", text="<p>World</p>")
        self.assertEqual(doc.Language(), "ca")

        self._copy_contents_of(doc, ["es"])

        manager = ITranslationManager(doc)
        self.assertTrue(manager.has_translation("es"))
        translated = manager.get_translation("es")
        self.assertEqual(translated.Title(), "Hello")
        self.assertEqual(translated.text.raw, "<p>World</p>")
        self.assertEqual(translated.Language(), "es")

    def test_copy_contents_of_reuses_existing_translation(self):
        doc = self._create_document(title="Hello")
        manager = ITranslationManager(doc)
        translated = manager.add_translation("es")
        translated.title = "Outdated"

        doc.title = "Fresh"
        self._copy_contents_of(doc, ["es"])

        self.assertEqual(manager.get_translation("es").Title(), "Fresh")

    def test_copy_fields_dexterity_skips_language(self):
        doc = self._create_document(title="Hello")
        translated = ITranslationManager(doc).add_translation("es")

        ContentCopier(doc).copy_fields_dexterity(doc, translated)

        self.assertEqual(translated.Language(), "es")
        self.assertEqual(translated.title, "Hello")

    def test_copy_other_properties(self):
        doc = self._create_document()
        translated = ITranslationManager(doc).add_translation("es")
        copier = ContentCopier(doc)

        doc.manage_addProperty("layout", "folder_listing", "string")
        copier.copy_other_properties(doc, translated)
        self.assertTrue(translated.hasProperty("layout"))
        self.assertEqual(translated.getProperty("layout"), "folder_listing")

        doc.manage_changeProperties(layout="summary_view")
        copier.copy_other_properties(doc, translated)
        self.assertEqual(translated.getProperty("layout"), "summary_view")

    def test_copy_seo_properties(self):
        doc = self._create_document()
        translated = ITranslationManager(doc).add_translation("es")
        copier = ContentCopier(doc)

        doc.manage_addProperty("qSEO_title", "SEO title", "string")
        doc.manage_addProperty("qSEO_keywords", ["one", "two"], "lines")
        copier.copy_seo_properties(doc, translated)

        self.assertEqual(translated.getProperty("qSEO_title"), "SEO title")
        self.assertEqual(translated.getProperty("qSEO_keywords"), ("one", "two"))

        doc.manage_changeProperties(qSEO_title="Updated title")
        copier.copy_seo_properties(doc, translated)
        self.assertEqual(translated.getProperty("qSEO_title"), "Updated title")

    def test_copy_other_things_calls_adapters(self):
        class DummyTranslator:
            def __init__(self, source, target):
                self.source = source
                self.target = target

            def translate(self):
                self.target.title = "Handled by adapter"

        gsm = getGlobalSiteManager()
        gsm.registerAdapter(
            DummyTranslator,
            (IDexterityContent, IDexterityContent),
            ITranslateThings,
            name="dummy-translator",
        )
        try:
            doc = self._create_document(title="Hello")
            translated = ITranslationManager(doc).add_translation("es")
            ContentCopier(doc).copy_other_things(doc, translated)
            self.assertEqual(translated.title, "Handled by adapter")
        finally:
            gsm.unregisterAdapter(
                DummyTranslator,
                (IDexterityContent, IDexterityContent),
                ITranslateThings,
                name="dummy-translator",
            )

    def test_change_content_richtext(self):
        doc = self._create_document(text="<p>Hello</p>")
        translated = ITranslationManager(doc).add_translation("es")

        ContentCopier(doc).change_content(doc, translated, "text")

        self.assertEqual(translated.text.raw, "<p>Hello</p>")

    def test_change_content_relationlist(self):
        related = self._create_document(title="Related")
        doc = self._create_document(title="Main")
        ITranslationManager(related).add_translation("es")
        translated = ITranslationManager(doc).add_translation("es")

        intids = getUtility(IIntIds)
        try:
            related_id = intids.getId(related)
        except KeyError:
            related_id = intids.register(related)
        doc.relatedItems = [RelationValue(related_id)]

        ContentCopier(doc).change_content(
            doc, translated, "relatedItems", IRelatedItems["relatedItems"]
        )

        related_es = ITranslationManager(related).get_translation("es")
        self.assertEqual(len(translated.relatedItems), 1)
        self.assertEqual(translated.relatedItems[0].to_object, related_es)

    def test_copy_contents_of_skips_lif(self):
        brains = self.portal.portal_catalog(portal_type="LIF")
        self.assertTrue(brains, "No LIF found in the test fixture")
        lif = brains[0].getObject()
        self.assertEqual(lif.portal_type, "LIF")

        self._copy_contents_of(lif, ["es"])

        self.assertFalse(ITranslationManager(lif).has_translation("es"))

    # copy_content_to (button handler)

    def test_copy_content_to_include_context(self):
        doc = self._create_document(title="Hello")

        self._run_handler(
            doc,
            {
                "target_languages": ["es"],
                "include_context": True,
                "include_children": False,
            },
        )

        self.assertTrue(ITranslationManager(doc).has_translation("es"))
        messages = IStatusMessage(self.request).show()
        self.assertTrue(any(message.type == "info" for message in messages))

    def test_copy_content_to_include_children(self):
        folder = createContentInContainer(self.ca, "Folder", title="Folder")
        child = createContentInContainer(folder, "Document", title="Child")

        self._run_handler(
            folder,
            {
                "target_languages": ["es"],
                "include_context": True,
                "include_children": True,
            },
        )

        folder_manager = ITranslationManager(folder)
        self.assertTrue(folder_manager.has_translation("es"))
        folder_es = folder_manager.get_translation("es")

        child_manager = ITranslationManager(child)
        self.assertTrue(child_manager.has_translation("es"))
        self.assertEqual(folder_es[child.getId()], child_manager.get_translation("es"))

    def test_copy_content_to_validation_error(self):
        doc = self._create_document()
        form = self._form_for(doc)
        form.extractData = lambda: ({}, [object()])

        form.copy_content_to(form, None)

        self.assertFalse(ITranslationManager(doc).has_translation("es"))
        self.assertTrue(form.status)
