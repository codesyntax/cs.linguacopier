# -*- coding: utf-8 -*-
"""Setup tests for this package."""
from plone import api
from cs.linguacopier.testing import CS_LINGUACOPIER_INTEGRATION_TESTING  # noqa

import unittest


class TestSetup(unittest.TestCase):
    """Test that cs.linguacopier is properly installed."""

    layer = CS_LINGUACOPIER_INTEGRATION_TESTING

    def setUp(self):
        """Custom shared utility setup for tests."""
        self.portal = self.layer['portal']
        self.installer = api.portal.get_tool('portal_quickinstaller')

    def test_product_installed(self):
        """Test if cs.linguacopier is installed."""
        self.assertTrue(self.installer.isProductInstalled(
            'cs.linguacopier'))

    def test_browserlayer(self):
        """Test that ICsLinguacopierLayer is registered."""
        from cs.linguacopier.interfaces import (
            ICsLinguacopierLayer)
        from plone.browserlayer import utils
        self.assertIn(ICsLinguacopierLayer, utils.registered_layers())


class TestUninstall(unittest.TestCase):

    layer = CS_LINGUACOPIER_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        self.installer = api.portal.get_tool('portal_quickinstaller')
        self.installer.uninstallProducts(['cs.linguacopier'])

    def test_product_uninstalled(self):
        """Test if cs.linguacopier is cleanly uninstalled."""
        self.assertFalse(self.installer.isProductInstalled(
            'cs.linguacopier'))

    def test_browserlayer_removed(self):
        """Test that ICsLinguacopierLayer is removed."""
        from cs.linguacopier.interfaces import \
            ICsLinguacopierLayer
        from plone.browserlayer import utils
        self.assertNotIn(ICsLinguacopierLayer, utils.registered_layers())
