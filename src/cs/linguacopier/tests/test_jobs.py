"""Tests for the persistent background copy job queue."""

from cs.linguacopier.interfaces import ICopyJobQueue
from cs.linguacopier.jobs import CANCELLED
from cs.linguacopier.jobs import DONE
from cs.linguacopier.jobs import get_job_store
from cs.linguacopier.jobs import QUEUED
from cs.linguacopier.jobs import RUNNING
from cs.linguacopier.testing import CS_LINGUACOPIER_FUNCTIONAL_TESTING
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from zope.component import getUtility

import unittest


class TestCopyJobQueue(unittest.TestCase):
    layer = CS_LINGUACOPIER_FUNCTIONAL_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        self.queue = getUtility(ICopyJobQueue)

    def _params(self, **overrides):
        params = {
            "context_path": ["plone", "ca"],
            "target_languages": ["es"],
            "include_context": True,
            "include_children": False,
            "translate": False,
        }
        params.update(overrides)
        return params

    def test_add_creates_a_queued_job(self):
        job = self.queue.add(self._params(), requested_by="bob")

        self.assertEqual(job.status, QUEUED)
        self.assertEqual(job.requested_by, "bob")
        self.assertEqual(job.params["target_languages"], ["es"])
        self.assertEqual(job.progress["processed"], 0)
        self.assertEqual(job.progress["total"], 0)

    def test_get_returns_the_job(self):
        job = self.queue.add(self._params())

        self.assertIs(self.queue.get(job.id), job)

    def test_get_unknown_job_is_none(self):
        self.assertIsNone(self.queue.get("does-not-exist"))

    def test_all_lists_newest_first(self):
        first = self.queue.add(self._params())
        second = self.queue.add(self._params())

        self.assertEqual([job.id for job in self.queue.all()], [second.id, first.id])

    def test_pending_lists_queued_and_running_oldest_first(self):
        first = self.queue.add(self._params())
        second = self.queue.add(self._params())
        third = self.queue.add(self._params())
        first.status = DONE
        second.status = RUNNING

        self.assertEqual(
            [job.id for job in self.queue.pending()], [second.id, third.id]
        )

    def test_cancel_a_queued_job(self):
        job = self.queue.add(self._params())

        cancelled = self.queue.cancel(job.id)

        self.assertEqual(cancelled.status, CANCELLED)
        self.assertIsNotNone(cancelled.finished)

    def test_cancel_a_running_job_requests_it(self):
        job = self.queue.add(self._params())
        job.status = RUNNING

        self.queue.cancel(job.id)

        self.assertTrue(job.cancel_requested)
        self.assertEqual(job.status, RUNNING)

    def test_cancel_unknown_job_is_none(self):
        self.assertIsNone(self.queue.cancel("does-not-exist"))

    def test_store_survives_a_new_queue_utility(self):
        job = self.queue.add(self._params())

        store = get_job_store(self.portal)

        self.assertIn(job.id, store.jobs)

    def test_to_dict(self):
        job = self.queue.add(self._params(), requested_by="bob")

        data = job.to_dict()

        self.assertEqual(data["status"], QUEUED)
        self.assertEqual(data["requested_by"], "bob")
        self.assertEqual(data["params"]["target_languages"], ["es"])
        self.assertIn("progress", data)
        self.assertEqual(data["errors"], [])
