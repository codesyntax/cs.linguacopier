"""Functional tests for the @copy-content-to REST service."""

from cs.linguacopier.interfaces import ITranslateThings
from cs.linguacopier.testing import CS_LINGUACOPIER_RESTAPI_FUNCTIONAL_TESTING
from cs.linguacopier.testing import FakeTranslationService
from plone.app.multilingual.interfaces import ITranslationManager

try:
    from plone.app.multilingual.interfaces import IExternalTranslationService
except ImportError:
    IExternalTranslationService = None

from plone.app.testing import setRoles
from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import SITE_OWNER_PASSWORD
from plone.app.testing import TEST_USER_ID
from plone.dexterity.interfaces import IDexterityContent
from plone.dexterity.utils import createContentInContainer
from urllib.parse import urljoin
from urllib.parse import urlparse
from zope.component import getGlobalSiteManager

import requests
import transaction
import unittest


class RelativeSession(requests.Session):
    """A requests session that resolves relative URLs against a base URL.

    A local stand-in for ``plone.restapi.testing.RelativeSession``, which would
    pull in ``collective.MockMailHost``.
    """

    def __init__(self, base_url, test=None):
        super().__init__()
        if not base_url.endswith("/"):
            base_url += "/"
        self._base_url = base_url
        if hasattr(test, "addCleanup"):
            test.addCleanup(self.close)

    def request(self, method, url, **kwargs):
        if urlparse(url).scheme not in ("http", "https"):
            url = urljoin(self._base_url, url.lstrip("/"))
        return super().request(method, url, **kwargs)


class TestCopyContentTo(unittest.TestCase):
    layer = CS_LINGUACOPIER_RESTAPI_FUNCTIONAL_TESTING

    def setUp(self):
        self.app = self.layer["app"]
        self.portal = self.layer["portal"]
        self.portal_url = self.portal.absolute_url()
        self.ca = self.portal["ca"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])

        self.api_session = RelativeSession(self.portal_url, test=self)
        self.api_session.headers.update({"Accept": "application/json"})
        self.api_session.auth = (SITE_OWNER_NAME, SITE_OWNER_PASSWORD)

    def tearDown(self):
        self.api_session.close()

    def _create_document(self, container=None, title="A document"):
        container = container if container is not None else self.ca
        doc = createContentInContainer(container, "Document", title=title)
        transaction.commit()
        return doc

    def _endpoint(self, obj):
        return f"{obj.absolute_url()}/@copy-content-to"

    def _abort(self):
        # The request ran in the server's thread and committed; drop the test
        # thread's transaction so its reads see the new state.
        transaction.abort()

    @unittest.skipUnless(
        IExternalTranslationService, "external translation API not installed"
    )
    def test_translate_true_translates_content(self):
        doc = self._create_document(title="Hello")
        service = FakeTranslationService()
        gsm = getGlobalSiteManager()
        gsm.registerUtility(
            service, IExternalTranslationService, name="test-translator"
        )
        try:
            response = self.api_session.post(
                self._endpoint(doc),
                json={
                    "target_languages": ["es"],
                    "include_context": True,
                    "translate": True,
                },
            )
        finally:
            gsm.unregisterUtility(
                service, IExternalTranslationService, name="test-translator"
            )
        self._abort()

        self.assertEqual(response.status_code, 200)
        translated = ITranslationManager(doc).get_translation("es")
        self.assertEqual(translated.title, "[es] Hello")

    @unittest.skipUnless(
        IExternalTranslationService, "external translation API not installed"
    )
    def test_translate_true_without_service_keeps_content(self):
        doc = self._create_document(title="Hello")

        response = self.api_session.post(
            self._endpoint(doc),
            json={
                "target_languages": ["es"],
                "include_context": True,
                "translate": True,
            },
        )
        self._abort()

        self.assertEqual(response.status_code, 200)
        translated = ITranslationManager(doc).get_translation("es")
        self.assertEqual(translated.title, "Hello")

    @unittest.skipUnless(
        IExternalTranslationService, "external translation API not installed"
    )
    def test_translation_outcome_translated(self):
        doc = self._create_document(title="Hello")
        service = FakeTranslationService()
        gsm = getGlobalSiteManager()
        gsm.registerUtility(
            service, IExternalTranslationService, name="test-translator"
        )
        try:
            response = self.api_session.post(
                self._endpoint(doc),
                json={
                    "target_languages": ["es"],
                    "include_context": True,
                    "translate": True,
                },
            )
        finally:
            gsm.unregisterUtility(
                service, IExternalTranslationService, name="test-translator"
            )
        self._abort()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["copied"][0]["translation"], "translated")

    @unittest.skipUnless(
        IExternalTranslationService, "external translation API not installed"
    )
    def test_translation_outcome_partial(self):
        doc = self._create_document(title="Hello")
        doc.description = "World"
        transaction.commit()
        service = FakeTranslationService(skip={"World"})
        gsm = getGlobalSiteManager()
        gsm.registerUtility(
            service, IExternalTranslationService, name="test-translator"
        )
        try:
            response = self.api_session.post(
                self._endpoint(doc),
                json={
                    "target_languages": ["es"],
                    "include_context": True,
                    "translate": True,
                },
            )
        finally:
            gsm.unregisterUtility(
                service, IExternalTranslationService, name="test-translator"
            )
        self._abort()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["copied"][0]["translation"], "partial")

    @unittest.skipUnless(
        IExternalTranslationService, "external translation API not installed"
    )
    def test_translation_outcome_not_translated_without_service(self):
        doc = self._create_document(title="Hello")

        response = self.api_session.post(
            self._endpoint(doc),
            json={
                "target_languages": ["es"],
                "include_context": True,
                "translate": True,
            },
        )
        self._abort()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["copied"][0]["translation"], "not_translated")

    def test_no_translation_outcome_when_not_requested(self):
        doc = self._create_document(title="Hello")

        response = self.api_session.post(
            self._endpoint(doc),
            json={"target_languages": ["es"], "include_context": True},
        )
        self._abort()

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("translation", response.json()["copied"][0])

    def test_copy_context_to_language(self):
        doc = self._create_document(title="Hello")

        response = self.api_session.post(
            self._endpoint(doc),
            json={"target_languages": ["es"], "include_context": True},
        )
        self._abort()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["@id"], doc.absolute_url())
        self.assertEqual(payload["target_languages"], ["es"])
        translated = ITranslationManager(doc).get_translation("es")
        self.assertIsNotNone(translated)
        self.assertEqual(
            payload["copied"],
            [
                {
                    "@id": translated.absolute_url(),
                    "language": "es",
                    "status": "created",
                }
            ],
        )
        self.assertEqual(payload["errors"], [])

    def test_copy_children(self):
        folder = createContentInContainer(self.ca, "Folder", title="Folder")
        child = createContentInContainer(folder, "Document", title="Child")
        transaction.commit()

        response = self.api_session.post(
            self._endpoint(folder),
            json={
                "target_languages": ["es"],
                "include_context": True,
                "include_children": True,
            },
        )
        self._abort()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        statuses = {item["@id"]: item["status"] for item in payload["copied"]}
        folder_es = ITranslationManager(folder).get_translation("es")
        child_es = ITranslationManager(child).get_translation("es")
        self.assertIsNotNone(folder_es)
        self.assertIsNotNone(child_es)
        self.assertEqual(statuses[folder_es.absolute_url()], "created")
        self.assertEqual(statuses[child_es.absolute_url()], "created")
        self.assertEqual(payload["errors"], [])

    def test_validation_without_target_languages(self):
        doc = self._create_document()

        response = self.api_session.post(
            self._endpoint(doc),
            json={"target_languages": [], "include_context": True},
        )
        self._abort()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["copied"], [])
        self.assertEqual(len(payload["errors"]), 1)
        self.assertEqual(payload["errors"][0]["@id"], doc.absolute_url())
        self.assertNotIn("language", payload["errors"][0])
        self.assertFalse(ITranslationManager(doc).has_translation("es"))

    def test_validation_without_flags(self):
        doc = self._create_document()

        response = self.api_session.post(
            self._endpoint(doc),
            json={
                "target_languages": ["es"],
                "include_context": False,
                "include_children": False,
            },
        )
        self._abort()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["copied"], [])
        self.assertTrue(payload["errors"])
        self.assertFalse(ITranslationManager(doc).has_translation("es"))

    def test_unsupported_language(self):
        doc = self._create_document()

        response = self.api_session.post(
            self._endpoint(doc),
            json={"target_languages": ["zz"], "include_context": True},
        )
        self._abort()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["copied"], [])
        self.assertTrue(payload["errors"])
        self.assertFalse(ITranslationManager(doc).has_translation("es"))

    def test_cannot_copy_to_the_contents_own_language(self):
        doc = self._create_document()
        self.assertEqual(doc.Language(), "ca")

        response = self.api_session.post(
            self._endpoint(doc),
            json={"target_languages": ["ca"], "include_context": True},
        )
        self._abort()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["copied"], [])
        self.assertTrue(payload["errors"])
        self.assertIn("own language", payload["errors"][0]["message"])

    def test_permission_required(self):
        doc = self._create_document()
        anonymous = RelativeSession(self.portal_url, test=self)
        anonymous.headers.update({"Accept": "application/json"})

        response = anonymous.post(
            self._endpoint(doc),
            json={"target_languages": ["es"], "include_context": True},
        )
        self._abort()

        self.assertIn(response.status_code, (401, 403))
        self.assertFalse(ITranslationManager(doc).has_translation("es"))

    def test_partial_failure_is_reported(self):
        folder = createContentInContainer(self.ca, "Folder", title="Folder")
        good = createContentInContainer(folder, "Document", title="Good")
        bad = createContentInContainer(folder, "Document", title="Bad")
        transaction.commit()

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
            response = self.api_session.post(
                self._endpoint(folder),
                json={
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
        self._abort()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["copied"])
        self.assertEqual(len(payload["errors"]), 1)
        self.assertEqual(payload["errors"][0]["@id"], bad.absolute_url())
        self.assertEqual(payload["errors"][0]["language"], "es")
        self.assertIn("boom", payload["errors"][0]["message"])
        self.assertFalse(ITranslationManager(bad).has_translation("es"))
        self.assertTrue(ITranslationManager(good).has_translation("es"))
