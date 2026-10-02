"""Tests for the content copier."""

from cs.linguacopier.browser.copier import CopyContentToLanguage
from cs.linguacopier.browser.copier import ICopyContentToLanguage
from cs.linguacopier.browser.copier import report_counts
from cs.linguacopier.browser.copier import report_rows
from cs.linguacopier.copier import ContentCopier
from cs.linguacopier.copier import CopyError
from cs.linguacopier.copier import CopyReport
from cs.linguacopier.copier import CopyResult
from cs.linguacopier.copier import sort_by_physical_path_length
from cs.linguacopier.interfaces import ITranslateThings
from cs.linguacopier.testing import CS_LINGUACOPIER_FUNCTIONAL_TESTING
from cs.linguacopier.testing import CS_LINGUACOPIER_INTEGRATION_TESTING
from cs.linguacopier.testing import FakeTranslationService
from plone.app.dexterity.behaviors.metadata import IBasic
from plone.app.multilingual.dx.interfaces import ILanguageIndependentField
from plone.app.multilingual.interfaces import ITranslationManager


try:
    from plone.app.multilingual.interfaces import IExternalTranslationService
except ImportError:
    IExternalTranslationService = None

from plone.app.relationfield.behavior import IRelatedItems
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.app.textfield.value import RichTextValue
from plone.dexterity.interfaces import IDexterityContent
from plone.dexterity.utils import createContentInContainer
from Products.statusmessages.interfaces import IStatusMessage
from unittest import mock
from z3c.form.interfaces import WidgetActionExecutionError
from z3c.relationfield import RelationValue
from zope.component import getGlobalSiteManager
from zope.component import getUtility
from zope.interface import alsoProvides
from zope.interface import noLongerProvides
from zope.intid.interfaces import IIntIds
from zope.schema.interfaces import IVocabularyFactory

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
        self.assertTrue(ICopyContentToLanguage["include_context"].default)
        self.assertTrue(ICopyContentToLanguage["include_children"].default)
        self.assertTrue(ICopyContentToLanguage["target_languages"].required)


class TestReportViewModel(unittest.TestCase):
    def _report(self):
        target = DummyContent(("plone", "es", "good"))
        source = DummyContent(("plone", "ca", "bad"))
        return CopyReport(
            successes=[
                CopyResult(target=target, language="es", status="created"),
                CopyResult(target=target, language="ca", status="updated"),
                CopyResult(target=target, language="es", status="skipped"),
            ],
            errors=[CopyError(source=source, language="es", message="boom")],
        )

    def test_report_counts(self):
        self.assertEqual(
            report_counts(self._report()),
            {"created": 1, "updated": 1, "skipped": 1, "failed": 1},
        )

    def test_report_rows(self):
        report = self._report()
        rows = report_rows(report)

        self.assertEqual(len(rows), 4)
        self.assertEqual(
            {row["status"] for row in rows},
            {"created", "updated", "skipped", "failed"},
        )
        failure = [row for row in rows if row["status"] == "failed"][0]
        self.assertEqual(failure["object"], report.errors[0].source)
        self.assertEqual(failure["language"], "es")
        self.assertEqual(failure["message"], "boom")

    def test_none_report_is_tolerated(self):
        # the form template evaluates the counts before its condition guard,
        # i.e. on the initial GET too, when no copy has run yet
        self.assertEqual(
            report_counts(None),
            {"created": 0, "updated": 0, "skipped": 0, "failed": 0},
        )
        self.assertEqual(report_rows(None), [])


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

    def _copy(self, obj, languages):
        return ContentCopier(obj).copy(languages, include_context=True)

    def _run_handler(self, obj, data, errors=None):
        form = self._form_for(obj)
        form.extractData = lambda: (data, errors or [])
        form.copy_content_to(form, None)
        return form

    # copy_contents_of / copy pipeline

    def test_copy_creates_translation(self):
        doc = self._create_document(title="Hello", text="<p>World</p>")
        self.assertEqual(doc.Language(), "ca")

        report = self._copy(doc, ["es"])

        manager = ITranslationManager(doc)
        self.assertTrue(manager.has_translation("es"))
        translated = manager.get_translation("es")
        self.assertEqual(translated.Title(), "Hello")
        self.assertEqual(translated.text.raw, "<p>World</p>")
        self.assertEqual(translated.Language(), "es")
        self.assertEqual([r.status for r in report.successes], ["created"])
        self.assertEqual(report.errors, [])

    def test_copy_updates_existing_translation(self):
        doc = self._create_document(title="Hello")
        manager = ITranslationManager(doc)
        translated = manager.add_translation("es")
        translated.title = "Outdated"

        doc.title = "Fresh"
        report = self._copy(doc, ["es"])

        self.assertEqual(manager.get_translation("es").Title(), "Fresh")
        self.assertEqual([r.status for r in report.successes], ["updated"])

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

    def test_copy_reports_skipped_lif(self):
        brains = self.portal.portal_catalog(portal_type="LIF")
        self.assertTrue(brains, "No LIF found in the test fixture")
        lif = brains[0].getObject()
        self.assertEqual(lif.portal_type, "LIF")

        report = self._copy(lif, ["es"])

        self.assertEqual([r.status for r in report.successes], ["skipped"])
        self.assertEqual(report.successes[0].target, lif)
        self.assertFalse(ITranslationManager(lif).has_translation("es"))

    def test_copy_is_best_effort_and_rolls_back_the_failed_object(self):
        class ExplodingTranslator:
            def __init__(self, source, target):
                self.source = source

            def translate(self):
                if self.source.title == "Bad":
                    raise ValueError("boom")

        gsm = getGlobalSiteManager()
        gsm.registerAdapter(
            ExplodingTranslator,
            (IDexterityContent, IDexterityContent),
            ITranslateThings,
            name="exploding-translator",
        )
        try:
            folder = createContentInContainer(self.ca, "Folder", title="Folder")
            good = createContentInContainer(folder, "Document", title="Good")
            bad = createContentInContainer(folder, "Document", title="Bad")

            report = ContentCopier(folder).copy(
                ["es"], include_context=True, include_children=True
            )
        finally:
            gsm.unregisterAdapter(
                ExplodingTranslator,
                (IDexterityContent, IDexterityContent),
                ITranslateThings,
                name="exploding-translator",
            )

        # the failing object is recorded with its source, language and message
        self.assertEqual(len(report.errors), 1)
        error = report.errors[0]
        self.assertEqual(error.source, bad)
        self.assertEqual(error.language, "es")
        self.assertIn("boom", error.message)

        # its savepoint rolled back: no half-copied translation is left behind
        self.assertFalse(ITranslationManager(bad).has_translation("es"))

        # the rest of the copy still went through
        self.assertTrue(ITranslationManager(folder).has_translation("es"))
        self.assertTrue(ITranslationManager(good).has_translation("es"))
        statuses = {r.target.getId(): r.status for r in report.successes}
        self.assertEqual(statuses["folder"], "created")
        self.assertEqual(statuses["good"], "created")

    def test_copy_records_a_field_failure_and_rolls_back(self):
        doc = self._create_document(title="Hello")

        def explode(self, source, target, key, field=None, translatable=True):
            raise ValueError(f"cannot copy {key}")

        with mock.patch.object(ContentCopier, "change_content", explode):
            report = ContentCopier(doc).copy(["es"], include_context=True)

        # a field-copy failure is no longer swallowed: it is reported and the
        # object's savepoint is rolled back, so no half-copied translation stays
        self.assertEqual(len(report.errors), 1)
        self.assertEqual(report.errors[0].source, doc)
        self.assertEqual(report.errors[0].language, "es")
        self.assertIn("cannot copy", report.errors[0].message)
        self.assertFalse(ITranslationManager(doc).has_translation("es"))

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

    def test_copy_content_to_requires_target_languages(self):
        doc = self._create_document()
        form = self._form_for(doc)
        form.extractData = lambda: ({"target_languages": []}, [])

        with self.assertRaises(WidgetActionExecutionError):
            form.copy_content_to(form, None)

        self.assertFalse(ITranslationManager(doc).has_translation("es"))

    def test_copy_content_to_builds_a_report(self):
        doc = self._create_document(title="Hello")

        form = self._run_handler(
            doc,
            {
                "target_languages": ["es"],
                "include_context": True,
                "include_children": False,
            },
        )

        self.assertIsNotNone(form.report)
        self.assertEqual(form.report_counts["created"], 1)
        self.assertEqual(form.report_rows[0]["status"], "created")

    def test_copy_content_to_report_includes_failures(self):
        class ExplodingTranslator:
            def __init__(self, source, target):
                self.source = source

            def translate(self):
                if self.source.title == "Bad":
                    raise ValueError("boom")

        gsm = getGlobalSiteManager()
        gsm.registerAdapter(
            ExplodingTranslator,
            (IDexterityContent, IDexterityContent),
            ITranslateThings,
            name="exploding-translator",
        )
        try:
            folder = createContentInContainer(self.ca, "Folder", title="Folder")
            createContentInContainer(folder, "Document", title="Good")
            createContentInContainer(folder, "Document", title="Bad")
            form = self._run_handler(
                folder,
                {
                    "target_languages": ["es"],
                    "include_context": True,
                    "include_children": True,
                },
            )
        finally:
            gsm.unregisterAdapter(
                ExplodingTranslator,
                (IDexterityContent, IDexterityContent),
                ITranslateThings,
                name="exploding-translator",
            )

        self.assertEqual(form.report_counts["failed"], 1)
        failed = [row for row in form.report_rows if row["status"] == "failed"]
        self.assertEqual(len(failed), 1)
        self.assertIn("boom", failed[0]["message"])

    def test_report_is_rendered_on_the_form(self):
        doc = self._create_document(title="Hello")
        form = self._form_for(doc)
        form.update()
        form.extractData = lambda: (
            {
                "target_languages": ["es"],
                "include_context": True,
                "include_children": False,
            },
            [],
        )
        form.copy_content_to(form, None)

        html = form.render()

        self.assertIn("linguacopier-report-items", html)
        self.assertIn("Export as CSV", html)
        self.assertIn("cs.linguacopier.export.js", html)

    def test_form_renders_without_a_report(self):
        doc = self._create_document(title="Hello")
        form = self._form_for(doc)
        form.update()

        html = form.render()

        self.assertNotIn("linguacopier-report-items", html)

    def _target_languages(self, context):
        factory = getUtility(
            IVocabularyFactory, "cs.linguacopier.AvailableTargetLanguages"
        )
        return {term.value for term in factory(context)}

    def test_target_languages_exclude_the_context_language(self):
        doc = self._create_document()
        self.assertEqual(doc.Language(), "ca")

        values = self._target_languages(doc)

        self.assertIn("es", values)
        self.assertNotIn("ca", values)

    def test_language_independent_context_offers_all_languages(self):
        # the portal root has no language, so nothing is excluded
        values = self._target_languages(self.portal)

        self.assertIn("ca", values)
        self.assertIn("es", values)

    def test_form_hides_when_there_is_nothing_to_copy_to(self):
        doc = self._create_document(title="Hello")
        form = self._form_for(doc)

        with mock.patch(
            "cs.linguacopier.languages.has_target_languages",
            lambda context: False,
        ):
            form.update()
            html = form.render()

        self.assertIn("There are no other languages", html)
        self.assertNotIn("form.widgets.target_languages", html)


class TestCopyTransaction(unittest.TestCase):
    layer = CS_LINGUACOPIER_INTEGRATION_TESTING

    def test_copy_does_not_commit(self):
        portal = self.layer["portal"]
        setRoles(portal, TEST_USER_ID, ["Manager"])
        doc = createContentInContainer(portal["ca"], "Document", title="Hello")

        report = ContentCopier(doc).copy(["es"], include_context=True)

        # IntegrationTesting replaces transaction.commit with a guard that
        # raises; reaching here proves the pipeline never commits mid-request.
        self.assertEqual([r.status for r in report.successes], ["created"])
        self.assertTrue(ITranslationManager(doc).has_translation("es"))


@unittest.skipUnless(
    IExternalTranslationService, "external translation API not installed"
)
class TestTranslateOnCopy(unittest.TestCase):
    layer = CS_LINGUACOPIER_FUNCTIONAL_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        self.ca = self.portal["ca"]
        self.service = FakeTranslationService()
        getGlobalSiteManager().registerUtility(
            self.service, IExternalTranslationService, name="test-translator"
        )

    def tearDown(self):
        getGlobalSiteManager().unregisterUtility(
            self.service, IExternalTranslationService, name="test-translator"
        )

    def _document(self, **kwargs):
        return createContentInContainer(self.ca, "Document", **kwargs)

    def test_translates_scalar_text_fields(self):
        doc = self._document(title="Hello", description="World")

        ContentCopier(doc).copy(["es"], include_context=True, translate=True)

        translated = ITranslationManager(doc).get_translation("es")
        self.assertEqual(translated.title, "[es] Hello")
        self.assertEqual(translated.description, "[es] World")

    def test_translate_off_keeps_values(self):
        doc = self._document(title="Hello", description="World")

        ContentCopier(doc).copy(["es"], include_context=True)

        translated = ITranslationManager(doc).get_translation("es")
        self.assertEqual(translated.title, "Hello")
        self.assertEqual(translated.description, "World")
        self.assertEqual(self.service.calls, [])

    def test_translates_rich_text_and_preserves_markup(self):
        doc = self._document(
            title="Hello",
            text=RichTextValue(
                "<p>Hello <strong>world</strong></p>", "text/html", "text/x-html-safe"
            ),
        )

        ContentCopier(doc).copy(["es"], include_context=True, translate=True)

        translated = ITranslationManager(doc).get_translation("es")
        self.assertEqual(
            translated.text.raw, "[es] <p>Hello <strong>world</strong></p>"
        )
        # the raw HTML is what is fed to the service
        self.assertIn(
            ("<p>Hello <strong>world</strong></p>", "ca", "es"), self.service.calls
        )

    def test_empty_rich_text_is_not_translated(self):
        doc = self._document(
            title="Hello",
            text=RichTextValue("", "text/html", "text/x-html-safe"),
        )

        ContentCopier(doc).copy(["es"], include_context=True, translate=True)

        self.assertNotIn("", [call[0] for call in self.service.calls])

    def test_translate_off_keeps_rich_text(self):
        doc = self._document(
            title="Hello",
            text=RichTextValue("<p>Hello</p>", "text/html", "text/x-html-safe"),
        )

        ContentCopier(doc).copy(["es"], include_context=True)

        translated = ITranslationManager(doc).get_translation("es")
        self.assertEqual(translated.text.raw, "<p>Hello</p>")
        self.assertEqual(self.service.calls, [])

    def test_language_independent_field_is_not_translated(self):
        doc = self._document(title="Hello", description="World")
        field = IBasic["title"]
        alsoProvides(field, ILanguageIndependentField)
        try:
            ContentCopier(doc).copy(["es"], include_context=True, translate=True)
        finally:
            noLongerProvides(field, ILanguageIndependentField)

        translated = ITranslationManager(doc).get_translation("es")
        # the language-independent title is copied, not translated
        self.assertEqual(translated.title, "Hello")
        # an ordinary field on the same object is translated
        self.assertEqual(translated.description, "[es] World")

    def test_empty_values_are_not_translated(self):
        doc = self._document(title="Hello", description="")

        ContentCopier(doc).copy(["es"], include_context=True, translate=True)

        self.assertTrue(self.service.calls)
        self.assertNotIn("", [call[0] for call in self.service.calls])

    def test_string_lists_are_not_translated(self):
        doc = self._document(title="Hello")
        doc.subjects = ("one", "two")
        self.assertIn("one", doc.subjects)

        ContentCopier(doc).copy(["es"], include_context=True, translate=True)

        self.assertNotIn("one", [call[0] for call in self.service.calls])


@unittest.skipUnless(
    IExternalTranslationService, "external translation API not installed"
)
class TestTranslateFallback(unittest.TestCase):
    layer = CS_LINGUACOPIER_FUNCTIONAL_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        self.ca = self.portal["ca"]

    def test_no_service_keeps_original_values(self):
        doc = createContentInContainer(self.ca, "Document", title="Hello")

        ContentCopier(doc).copy(["es"], include_context=True, translate=True)

        translated = ITranslationManager(doc).get_translation("es")
        self.assertEqual(translated.title, "Hello")
