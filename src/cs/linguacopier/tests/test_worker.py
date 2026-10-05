"""Tests for the background copy worker."""

from AccessControl.SecurityManagement import newSecurityManager
from AccessControl.users import nobody
from cs.linguacopier.copier import ContentCopier
from cs.linguacopier.interfaces import ICopyJobQueue
from cs.linguacopier.jobs import CANCELLED
from cs.linguacopier.jobs import DONE
from cs.linguacopier.jobs import FAILED
from cs.linguacopier.jobs import get_job_store
from cs.linguacopier.jobs import now
from cs.linguacopier.jobs import RUNNING
from cs.linguacopier.testing import CS_LINGUACOPIER_FUNCTIONAL_TESTING
from cs.linguacopier.testing import FakeTranslationService
from cs.linguacopier.worker import process_pending_jobs
from datetime import timedelta
from plone.app.multilingual.interfaces import ITranslationManager
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.dexterity.utils import createContentInContainer
from plone.registry.interfaces import IRegistry
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

    def _set_setting(self, name, value):
        registry = getUtility(IRegistry)
        registry[f"cs.linguacopier.{name}"] = value
        transaction.commit()

    def _folder_with_children(self, count):
        folder = createContentInContainer(self.ca, "Folder", title="Folder")
        for index in range(count):
            createContentInContainer(folder, "Document", title=f"Child {index}")
        return folder

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
        job = self._enqueue(folder, include_context=False, include_children=True)

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
        self.assertIn("boom", job.recent_errors()[0]["message"])
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

    def test_processes_the_whole_tree_in_chunks(self):
        folder = self._folder_with_children(3)
        self._set_setting("chunk_size", 1)
        job = self._enqueue(folder, include_context=False, include_children=True)

        process_pending_jobs(self.portal)

        job = self.queue.get(job.id)
        self.assertEqual(job.status, DONE)
        self.assertEqual(job.progress["processed"], 3)
        self.assertEqual(job.cursor, 3)

    def test_retries_a_failing_chunk_then_fails_the_job(self):
        doc = createContentInContainer(self.ca, "Document", title="Hello")
        self._set_setting("max_retries", 2)
        job = self._enqueue(doc)

        attempts = []

        def always_fail(self, item, language):
            attempts.append(item)
            raise ValueError("boom")

        with mock.patch.object(ContentCopier, "copy_item", always_fail):
            process_pending_jobs(self.portal)

        job = self.queue.get(job.id)
        self.assertEqual(job.status, FAILED)
        self.assertEqual(len(attempts), 3)  # the attempt plus two retries
        self.assertIn("boom", job.last_error)

    def test_resumes_a_running_job_from_its_cursor(self):
        folder = self._folder_with_children(3)
        self._set_setting("chunk_size", 1)
        job = self._enqueue(folder, include_context=False, include_children=True)
        # simulate a worker that stopped after committing the first chunk
        job.status = RUNNING
        job.cursor = 1
        job.progress["processed"] = 1
        transaction.commit()

        copied = []
        original = ContentCopier.copy_item

        def record(self, item, language):
            copied.append(item.getId())
            return original(self, item, language)

        with mock.patch.object(ContentCopier, "copy_item", record):
            process_pending_jobs(self.portal)

        job = self.queue.get(job.id)
        self.assertEqual(job.status, DONE)
        self.assertEqual(job.progress["processed"], 3)
        self.assertEqual(len(copied), 2)  # the first unit was not redone

    def test_running_job_stops_at_a_chunk_boundary_when_cancelled(self):
        folder = self._folder_with_children(3)
        self._set_setting("chunk_size", 1)
        job = self._enqueue(folder, include_context=False, include_children=True)

        copied = []
        original = ContentCopier.copy_item

        def cancel_after_first(self, item, language):
            result = original(self, item, language)
            copied.append(item)
            if len(copied) == 1:
                job.cancel_requested = True
            return result

        with mock.patch.object(ContentCopier, "copy_item", cancel_after_first):
            process_pending_jobs(self.portal)

        job = self.queue.get(job.id)
        self.assertEqual(job.status, CANCELLED)
        self.assertEqual(job.progress["processed"], 1)
        # the first chunk was committed before the cancellation took effect,
        # and the remaining items were left untouched
        self.assertTrue(ITranslationManager(copied[0]).has_translation("es"))
        not_copied = [child for child in folder.objectValues() if child not in copied]
        self.assertTrue(not_copied)
        self.assertFalse(ITranslationManager(not_copied[0]).has_translation("es"))

    def test_writes_a_heartbeat(self):
        store = get_job_store(self.portal)
        self.assertIsNone(store.worker_heartbeat)

        process_pending_jobs(self.portal)

        self.assertIsNotNone(store.worker_heartbeat)

    def test_refreshes_the_heartbeat_on_each_run(self):
        store = get_job_store(self.portal)
        store.worker_heartbeat = now() - timedelta(hours=1)
        transaction.commit()
        previous = store.worker_heartbeat

        process_pending_jobs(self.portal)

        self.assertGreater(store.worker_heartbeat, previous)

    def test_prunes_finished_jobs_past_retention(self):
        self._set_setting("job_retention_days", 0)
        job = self._enqueue(
            createContentInContainer(self.ca, "Document", title="Hello")
        )
        job.status = DONE
        job.finished = now() - timedelta(days=1)
        transaction.commit()

        process_pending_jobs(self.portal)

        self.assertIsNone(self.queue.get(job.id))

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
