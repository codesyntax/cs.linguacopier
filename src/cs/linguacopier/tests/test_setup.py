"""Setup tests for this package."""

import unittest

from plone import api
from plone.app.testing import TEST_USER_ID, setRoles
from plone.base.utils import get_installer

from cs.linguacopier.testing import CS_LINGUACOPIER_INTEGRATION_TESTING


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
        from plone.browserlayer import utils

        from cs.linguacopier.interfaces import ICsLinguacopierLayer

        self.assertIn(ICsLinguacopierLayer, utils.registered_layers())


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
        from plone.browserlayer import utils

        from cs.linguacopier.interfaces import ICsLinguacopierLayer

        self.assertNotIn(ICsLinguacopierLayer, utils.registered_layers())
