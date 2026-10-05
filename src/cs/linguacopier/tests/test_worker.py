"""Tests for the background copy worker."""

from AccessControl.SecurityManagement import newSecurityManager
from AccessControl.users import nobody
from cs.linguacopier.copier import ContentCopier
from cs.linguacopier.interfaces import ICopyJobQueue
from cs.linguacopier.jobs import DONE
from cs.linguacopier.jobs import FAILED
from cs.linguacopier.jobs import get_job_store
from cs.linguacopier.testing import CS_LINGUACOPIER_FUNCTIONAL_TESTING
from cs.linguacopier.testing import FakeTranslationService
from cs.linguacopier.worker import process_pending_jobs
from plone.app.multilingual.interfaces import ITranslationManager
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.dexterity.utils import createContentInContainer
from unittest import mock
from zope.component import getGlobalSiteManager
from zope.component import getUtility

import transaction
import unittest

try:
    from plone.app.multilingual.interfaces import IExternalTranslationService
except ImportError:
    IExternalTranslationService = None


class TestWorker(unittest.TestCase):
    layer = CS_LINGUACOPIER_FUNCTIONAL_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        self.ca = self.portal["ca"]
        self.queue = getUtility(ICopyJobQueue)

    def _enqueue(self, context, **overrides):
        params = {
            "context_path": list(context.getPhysicalPath()),
            "target_languages": ["es"],
            "include_context": True,
            "include_children": False,
            "translate": False,
        }
        params.update(overrides)
        job = self.queue.add(params, requested_by="tester")
        transaction.commit()
        return job

    def test_processes_a_queued_job(self):
        doc = createContentInContainer(self.ca, "Document", title="Hello")
        job = self._enqueue(doc)

        processed = process_pending_jobs(self.portal)

        self.assertEqual(processed, 1)
        job = self.queue.get(job.id)
        self.assertEqual(job.status, DONE)
        self.assertEqual(job.progress["created"], 1)
        self.assertEqual(job.progress["processed"], 1)
        self.assertEqual(job.progress["total"], 1)
        self.assertEqual(job.progress["failed"], 0)
        self.assertTrue(ITranslationManager(doc).has_translation("es"))

    def test_counts_the_whole_subtree(self):
        folder = createContentInContainer(self.ca, "Folder", title="Folder")
        createContentInContainer(folder, "Document", title="Child")
        job = self._enqueue(folder, include_children=True)

        process_pending_jobs(self.portal)

        job = self.queue.get(job.id)
        self.assertEqual(job.status, DONE)
        self.assertEqual(job.progress["total"], 2)
        self.assertEqual(job.progress["processed"], 2)

    def test_processes_only_queued_jobs(self):
        doc = createContentInContainer(self.ca, "Document", title="Hello")
        done = self._enqueue(doc)
        done.status = DONE
        transaction.commit()

        processed = process_pending_jobs(self.portal)

        self.assertEqual(processed, 0)

    def test_one_failing_object_does_not_abort_the_job(self):
        folder = createContentInContainer(self.ca, "Folder", title="Folder")
        createContentInContainer(folder, "Document", title="Good")
        createContentInContainer(folder, "Document", title="Bad")
        job = self._enqueue(folder, include_children=True)

        original = ContentCopier.copy_fields_dexterity

        def explode(self, source, target):
            if source.Title() == "Bad":
                raise ValueError("boom")
            return original(self, source, target)

        with mock.patch.object(ContentCopier, "copy_fields_dexterity", explode):
            process_pending_jobs(self.portal)

        job = self.queue.get(job.id)
        self.assertEqual(job.status, DONE)
        self.assertEqual(job.progress["failed"], 1)
        self.assertEqual(len(job.errors), 1)
        self.assertIn("boom", job.errors[0]["message"])
        # the good item still went through
        self.assertTrue(ITranslationManager(folder["good"]).has_translation("es"))

    def test_missing_context_marks_the_job_failed(self):
        job = self.queue.add(
            {
                "context_path": ["plone", "ca", "nope"],
                "target_languages": ["es"],
                "include_context": True,
                "include_children": False,
                "translate": False,
            }
        )
        transaction.commit()

        process_pending_jobs(self.portal)

        job = self.queue.get(job.id)
        self.assertEqual(job.status, FAILED)
        self.assertIsNotNone(job.last_error)

    def test_runs_as_the_site_owner_without_a_configured_user(self):
        doc = createContentInContainer(self.ca, "Document", title="Hello")
        job = self._enqueue(doc)

        # Become anonymous: only the worker's default elevation to the site
        # owner lets it create translations and finish the job.
        newSecurityManager(None, nobody)
        process_pending_jobs(self.portal)

        self.assertEqual(self.queue.get(job.id).status, DONE)
        self.assertTrue(ITranslationManager(doc).has_translation("es"))

    def test_writes_a_heartbeat(self):
        store = get_job_store(self.portal)
        self.assertIsNone(store.worker_heartbeat)

        process_pending_jobs(self.portal)

        self.assertIsNotNone(store.worker_heartbeat)

    @unittest.skipUnless(
        IExternalTranslationService, "external translation API not installed"
    )
    def test_records_the_translation_outcome(self):
        service = FakeTranslationService()
        gsm = getGlobalSiteManager()
        gsm.registerUtility(
            service, IExternalTranslationService, name="test-translator"
        )
        try:
            doc = createContentInContainer(self.ca, "Document", title="Hello")
            job = self._enqueue(doc, translate=True)
            process_pending_jobs(self.portal)
        finally:
            gsm.unregisterUtility(
                service, IExternalTranslationService, name="test-translator"
            )

        job = self.queue.get(job.id)
        self.assertEqual(job.translation["translated"], 1)
        translated = ITranslationManager(doc).get_translation("es")
        self.assertEqual(translated.title, "[es] Hello")
