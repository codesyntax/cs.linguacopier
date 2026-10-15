"""Setup tests for this package."""

from cs.linguacopier.testing import CS_LINGUACOPIER_INTEGRATION_TESTING
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.base.utils import get_installer
from plone.registry.interfaces import IRegistry
from zope.component import getUtility

import unittest


class TestSetup(unittest.TestCase):
    """Test that cs.linguacopier is properly installed."""

    layer = CS_LINGUACOPIER_INTEGRATION_TESTING

    def setUp(self):
        """Custom shared utility setup for tests."""
        self.portal = self.layer["portal"]
        self.installer = get_installer(self.portal, self.layer["request"])

    def test_product_installed(self):
        """Test if cs.linguacopier is installed."""
        self.assertTrue(self.installer.is_product_installed("cs.linguacopier"))

    def test_browserlayer(self):
        """Test that ICsLinguacopierLayer is registered."""
        from cs.linguacopier.interfaces import ICsLinguacopierLayer
        from plone.browserlayer import utils

        self.assertIn(ICsLinguacopierLayer, utils.registered_layers())

    def test_profile_is_at_the_control_panel_upgrade_version(self):
        self.assertEqual(
            self.portal.portal_setup.getLastVersionForProfile(
                "cs.linguacopier:default"
            ),
            ("1002",),
        )

    def test_upgrade_to_1002_registers_the_panels_and_settings(self):
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        setup = self.portal.portal_setup
        cptool = self.portal.portal_controlpanel
        registry = getUtility(IRegistry)

        # Undo the two things the 1002 step installs, as a site at 1001 has them.
        cptool.unregisterApplication("cs.linguacopier")
        for key in list(registry.records):
            if key.startswith("cs.linguacopier."):
                del registry.records[key]
        setup.setLastVersionForProfile("cs.linguacopier:default", "1001")

        setup.upgradeProfile("cs.linguacopier:default")

        ids = {configlet["id"] for configlet in cptool.enumConfiglets(group="Products")}
        records = {key for key in registry.records}

        self.assertIn("linguacopier-settings", ids)
        self.assertIn("linguacopier-jobs", ids)
        self.assertIn("cs.linguacopier.default_mode", records)

    def test_configlets_live_in_the_addon_configuration_group(self):
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        configlets = self.portal.portal_controlpanel.enumConfiglets(group="Products")
        ids = {configlet["id"] for configlet in configlets}

        self.assertIn("linguacopier-settings", ids)
        self.assertIn("linguacopier-jobs", ids)


class TestUninstall(unittest.TestCase):

    layer = CS_LINGUACOPIER_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.installer = get_installer(self.portal, self.layer["request"])
        roles_before = api.user.get_roles(TEST_USER_ID)
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        self.installer.uninstall_product("cs.linguacopier")
        setRoles(self.portal, TEST_USER_ID, roles_before)

    def test_product_uninstalled(self):
        """Test if cs.linguacopier is cleanly uninstalled."""
        self.assertFalse(self.installer.is_product_installed("cs.linguacopier"))

    def test_browserlayer_removed(self):
        """Test that ICsLinguacopierLayer is removed."""
        from cs.linguacopier.interfaces import ICsLinguacopierLayer
        from plone.browserlayer import utils

        self.assertNotIn(ICsLinguacopierLayer, utils.registered_layers())
