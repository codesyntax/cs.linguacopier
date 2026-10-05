"""Tests for the copy-mode planner (direct vs background routing)."""

from cs.linguacopier.planner import BACKGROUND
from cs.linguacopier.planner import DIRECT
from cs.linguacopier.planner import plan
from cs.linguacopier.settings import get_settings
from cs.linguacopier.testing import CS_LINGUACOPIER_FUNCTIONAL_TESTING
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.dexterity.utils import createContentInContainer
from plone.registry.interfaces import IRegistry
from zope.component import getUtility

import transaction
import unittest


class TestPlanner(unittest.TestCase):
    layer = CS_LINGUACOPIER_FUNCTIONAL_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        self.ca = self.portal["ca"]

    def _settings(self, threshold):
        registry = getUtility(IRegistry)
        registry["cs.linguacopier.direct_max_items"] = threshold
        transaction.commit()
        return get_settings()

    def _folder_with_children(self, count):
        folder = createContentInContainer(self.ca, "Folder", title="Folder")
        for index in range(count):
            createContentInContainer(folder, "Document", title=f"Child {index}")
        return folder

    def test_explicit_modes_are_honoured(self):
        doc = createContentInContainer(self.ca, "Document", title="Hello")
        settings = self._settings(1)

        self.assertEqual(plan(doc, "direct", ["es"], settings=settings), DIRECT)
        self.assertEqual(plan(doc, "background", ["es"], settings=settings), BACKGROUND)

    def test_a_falsy_mode_uses_the_configured_default(self):
        registry = getUtility(IRegistry)
        registry["cs.linguacopier.default_mode"] = "background"
        transaction.commit()
        doc = createContentInContainer(self.ca, "Document", title="Hello")

        self.assertEqual(plan(doc, None, ["es"]), BACKGROUND)

    def test_auto_without_translation_is_direct(self):
        folder = self._folder_with_children(5)
        settings = self._settings(1)

        self.assertEqual(
            plan(
                folder,
                "auto",
                ["es"],
                include_children=True,
                translate=False,
                settings=settings,
            ),
            DIRECT,
        )

    def test_auto_at_the_threshold_is_direct(self):
        # folder + one child = 2 items, one language, threshold 2 -> direct
        folder = self._folder_with_children(1)
        settings = self._settings(2)

        self.assertEqual(
            plan(
                folder,
                "auto",
                ["es"],
                include_context=True,
                include_children=True,
                translate=True,
                settings=settings,
            ),
            DIRECT,
        )

    def test_auto_over_the_threshold_is_background(self):
        # folder + one child = 2 items, one language, threshold 1 -> background
        folder = self._folder_with_children(1)
        settings = self._settings(1)

        self.assertEqual(
            plan(
                folder,
                "auto",
                ["es"],
                include_context=True,
                include_children=True,
                translate=True,
                settings=settings,
            ),
            BACKGROUND,
        )

    def test_target_languages_multiply_the_work(self):
        # one item, two languages = 2, threshold 1 -> background
        doc = createContentInContainer(self.ca, "Document", title="Hello")
        settings = self._settings(1)

        self.assertEqual(
            plan(
                doc,
                "auto",
                ["es", "eu"],
                include_context=True,
                translate=True,
                settings=settings,
            ),
            BACKGROUND,
        )
