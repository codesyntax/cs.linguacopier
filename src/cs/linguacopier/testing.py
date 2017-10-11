# -*- coding: utf-8 -*-
from plone.app.contenttypes.testing import PLONE_APP_CONTENTTYPES_FIXTURE
from plone.app.robotframework.testing import REMOTE_LIBRARY_BUNDLE_FIXTURE
from plone.app.testing import applyProfile
from plone.app.testing import FunctionalTesting
from plone.app.testing import IntegrationTesting
from plone.app.testing import PloneSandboxLayer
from plone.testing import z2

import cs.linguacopier


class CsLinguacopierLayer(PloneSandboxLayer):

    defaultBases = (PLONE_APP_CONTENTTYPES_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        # Load any other ZCML that is required for your tests.
        # The z3c.autoinclude feature is disabled in the Plone fixture base
        # layer.
        self.loadZCML(package=cs.linguacopier)

    def setUpPloneSite(self, portal):
        applyProfile(portal, 'cs.linguacopier:default')


CS_LINGUACOPIER_FIXTURE = CsLinguacopierLayer()


CS_LINGUACOPIER_INTEGRATION_TESTING = IntegrationTesting(
    bases=(CS_LINGUACOPIER_FIXTURE,),
    name='CsLinguacopierLayer:IntegrationTesting'
)


CS_LINGUACOPIER_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(CS_LINGUACOPIER_FIXTURE,),
    name='CsLinguacopierLayer:FunctionalTesting'
)


CS_LINGUACOPIER_ACCEPTANCE_TESTING = FunctionalTesting(
    bases=(
        CS_LINGUACOPIER_FIXTURE,
        REMOTE_LIBRARY_BUNDLE_FIXTURE,
        z2.ZSERVER_FIXTURE
    ),
    name='CsLinguacopierLayer:AcceptanceTesting'
)
