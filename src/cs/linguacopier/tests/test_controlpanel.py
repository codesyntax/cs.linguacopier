"""Smoke tests for the content copier control panels."""

from cs.linguacopier.browser.controlpanel import JobsView
from cs.linguacopier.browser.controlpanel import LinguacopierSettingsForm
from cs.linguacopier.interfaces import ICopyJobQueue
from cs.linguacopier.jobs import CANCELLED
from cs.linguacopier.jobs import DONE
from cs.linguacopier.jobs import get_job_store
from cs.linguacopier.jobs import now
from cs.linguacopier.jobs import QUEUED
from cs.linguacopier.jobs import RUNNING
from cs.linguacopier.settings import get_settings
from cs.linguacopier.testing import CS_LINGUACOPIER_FUNCTIONAL_TESTING
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.registry.interfaces import IRegistry
from zope.component import getUtility

import transaction
import unittest


class TestSettingsPanel(unittest.TestCase):
    layer = CS_LINGUACOPIER_FUNCTIONAL_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])

    def test_settings_are_read_from_and_written_to_the_registry(self):
        self.assertEqual(get_settings().direct_max_items, 20)

        registry = getUtility(IRegistry)
        registry["cs.linguacopier.direct_max_items"] = 5
        transaction.commit()

        self.assertEqual(get_settings().direct_max_items, 5)

    def test_settings_panel_renders_the_fields(self):
        form = LinguacopierSettingsForm(self.portal, self.request)
        form.update()

        html = form.render()

        self.assertIn("Default copy mode", html)
        self.assertIn("Direct copy size limit", html)
        self.assertIn("Worker user", html)

    def test_settings_panel_saves_to_the_registry(self):
        form = LinguacopierSettingsForm(self.portal, self.request)
        form.update()
        data, errors = form.extractData()
        data["direct_max_items"] = 7

        form.applyChanges(data)

        self.assertEqual(get_settings().direct_max_items, 7)


class TestJobsPanel(unittest.TestCase):
    layer = CS_LINGUACOPIER_FUNCTIONAL_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        self.queue = getUtility(ICopyJobQueue)

    def _job(self, **overrides):
        params = {
            "context_path": ["plone", "ca"],
            "target_languages": ["es"],
            "include_context": True,
            "include_children": False,
            "translate": False,
        }
        params.update(overrides)
        job = self.queue.add(params, requested_by="bob")
        transaction.commit()
        return job

    def _view(self):
        view = JobsView(self.portal, self.request)
        view.update()
        return view

    def test_panel_renders_jobs_and_actions(self):
        job = self._job()

        html = self._view()()

        self.assertIn(job.id, html)
        self.assertIn("Cancel", html)
        self.assertIn("Delete", html)

    def test_retry_button_shows_for_finished_jobs(self):
        job = self._job()
        job.status = DONE
        transaction.commit()

        html = self._view()()

        self.assertIn("Retry", html)

    def test_panel_warns_when_no_worker_has_run(self):
        html = self._view()()

        self.assertIn("No background worker", html)

    def test_panel_reports_a_fresh_heartbeat(self):
        get_job_store(self.portal).worker_heartbeat = now()
        transaction.commit()

        html = self._view()()

        self.assertIn("worker is running", html)

    def test_cancel_action_cancels_a_queued_job(self):
        job = self._job()

        self._view()._act("cancel", job.id)

        self.assertEqual(self.queue.get(job.id).status, CANCELLED)

    def test_delete_action_removes_a_job(self):
        job = self._job()

        self._view()._act("delete", job.id)

        self.assertIsNone(self.queue.get(job.id))

    def test_delete_action_refuses_a_running_job(self):
        job = self._job()
        job.status = RUNNING
        transaction.commit()

        self._view()._act("delete", job.id)

        self.assertIsNotNone(self.queue.get(job.id))

    def test_retry_action_requeues_a_finished_job(self):
        job = self._job()
        job.status = DONE
        transaction.commit()

        self._view()._act("retry", job.id)

        self.assertEqual(self.queue.get(job.id).status, QUEUED)
