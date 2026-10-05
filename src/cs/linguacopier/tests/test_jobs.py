"""Tests for the persistent background copy job queue."""

from BTrees.IOBTree import IOBTree
from BTrees.OOBTree import OOBTree
from cs.linguacopier.interfaces import ICopyJobQueue
from cs.linguacopier.jobs import CANCELLED
from cs.linguacopier.jobs import DONE
from cs.linguacopier.jobs import get_job_store
from cs.linguacopier.jobs import now
from cs.linguacopier.jobs import QUEUED
from cs.linguacopier.jobs import RUNNING
from cs.linguacopier.testing import CS_LINGUACOPIER_FUNCTIONAL_TESTING
from datetime import timedelta
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from zope.component import getUtility

import transaction
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

    def test_collections_are_btrees(self):
        job = self.queue.add(self._params())
        store = get_job_store(self.portal)

        self.assertIsInstance(store.jobs, OOBTree)
        self.assertIsInstance(store.order, IOBTree)
        self.assertIsInstance(job.params, OOBTree)
        self.assertIsInstance(job.progress, OOBTree)
        self.assertIsInstance(job.translation, OOBTree)
        self.assertIsInstance(job.errors, IOBTree)

    def test_errors_are_bounded(self):
        job = self.queue.add(self._params())

        for index in range(60):
            job.add_error("source", "es", f"error {index}")

        self.assertEqual(len(job.errors), 50)
        # the oldest are dropped, the newest kept
        self.assertEqual(job.recent_errors()[-1]["message"], "error 59")

    def test_order_is_kept_across_deletes(self):
        first = self.queue.add(self._params())
        second = self.queue.add(self._params())
        third = self.queue.add(self._params())
        second.status = DONE

        self.queue.delete(second.id)

        store = get_job_store(self.portal)
        self.assertNotIn(second.id, list(store.order.values()))
        self.assertEqual([job.id for job in self.queue.all()], [third.id, first.id])
        self.assertEqual([job.id for job in self.queue.pending()], [first.id, third.id])

    def test_to_dict(self):
        job = self.queue.add(self._params(), requested_by="bob")

        data = job.to_dict()

        self.assertEqual(data["status"], QUEUED)
        self.assertEqual(data["requested_by"], "bob")
        self.assertEqual(data["params"]["target_languages"], ["es"])
        self.assertIn("progress", data)
        self.assertEqual(data["errors"], [])

    def test_prune_removes_finished_jobs_older_than_retention(self):
        old = self.queue.add(self._params())
        old.status = DONE
        old.finished = now() - timedelta(days=40)
        recent = self.queue.add(self._params())
        recent.status = DONE
        recent.finished = now()
        transaction.commit()

        removed = self.queue.prune(retention_days=30)

        self.assertEqual(removed, [old.id])
        self.assertIsNone(self.queue.get(old.id))
        self.assertIsNotNone(self.queue.get(recent.id))

    def test_prune_keeps_queued_and_running_jobs(self):
        queued = self.queue.add(self._params())
        running = self.queue.add(self._params())
        running.status = RUNNING
        running.finished = now() - timedelta(days=40)

        self.queue.prune(retention_days=0, max_jobs=0)

        self.assertIsNotNone(self.queue.get(queued.id))
        self.assertIsNotNone(self.queue.get(running.id))

    def test_prune_enforces_the_maximum_count_keeping_the_newest(self):
        jobs = []
        for _ in range(3):
            job = self.queue.add(self._params())
            job.status = DONE
            job.finished = now()
            jobs.append(job)

        self.queue.prune(max_jobs=2)

        self.assertIsNone(self.queue.get(jobs[0].id))  # the oldest is dropped
        self.assertIsNotNone(self.queue.get(jobs[1].id))
        self.assertIsNotNone(self.queue.get(jobs[2].id))

    def test_prune_keeps_the_most_recently_finished_not_created(self):
        # An older job that finished last must survive a newer-created one.
        retried = self.queue.add(self._params())
        recent = self.queue.add(self._params())
        retried.status = DONE
        retried.finished = now()
        recent.status = DONE
        recent.finished = now() - timedelta(days=10)

        self.queue.prune(max_jobs=1)

        self.assertIsNotNone(self.queue.get(retried.id))
        self.assertIsNone(self.queue.get(recent.id))
