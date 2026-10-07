from plone.app.contenttypes.testing import PLONE_APP_CONTENTTYPES_FIXTURE
from plone.app.multilingual.dx.interfaces import ILanguageIndependentField
from plone.app.robotframework.testing import REMOTE_LIBRARY_BUNDLE_FIXTURE
from plone.app.testing import applyProfile
from plone.app.testing import FunctionalTesting
from plone.app.testing import IntegrationTesting
from plone.app.testing import PloneSandboxLayer
from plone.dexterity.interfaces import IDexterityFTI
from plone.testing import zope
from Products.CMFCore.utils import getToolByName
from zope.component import getUtility
from zope.configuration import xmlconfig
from zope.interface import alsoProvides

import cs.linguacopier
import plone.app.multilingual


class CsLinguacopierLayer(PloneSandboxLayer):

    defaultBases = (PLONE_APP_CONTENTTYPES_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        # Load any other ZCML that is required for your tests.
        # The z3c.autoinclude feature is disabled in the Plone fixture base
        # layer.
        xmlconfig.file(
            "testing.zcml", plone.app.multilingual, context=configurationContext
        )
        xmlconfig.file(
            "overrides.zcml", plone.app.multilingual, context=configurationContext
        )

        # Enable languageindependent-field on IRelatedItems-behavior
        from plone.app.relationfield.behavior import IRelatedItems

        alsoProvides(IRelatedItems["relatedItems"], ILanguageIndependentField)

        self.loadZCML(package=cs.linguacopier)
        # A test-only behavior with controlled (token) fields.
        self.loadZCML("configure.zcml", package=cs.linguacopier.tests)

    def setUpPloneSite(self, portal):
        # Define the languages before installing plone.app.multilingual so that
        # the corresponding language root folders are created.
        language_tool = getToolByName(portal, "portal_languages")
        language_tool.addSupportedLanguage("ca")
        language_tool.addSupportedLanguage("es")
        language_tool.use_request_negotiation = True

        applyProfile(portal, "plone.app.multilingual:default")
        applyProfile(portal, "cs.linguacopier:default")

        # Enable the test-only controlled-fields behavior on Document.
        fti = getUtility(IDexterityFTI, name="Document")
        if "cs.linguacopier.tests.categorized" not in fti.behaviors:
            fti.behaviors = tuple(fti.behaviors) + (
                "cs.linguacopier.tests.categorized",
            )


CS_LINGUACOPIER_FIXTURE = CsLinguacopierLayer()


CS_LINGUACOPIER_INTEGRATION_TESTING = IntegrationTesting(
    bases=(CS_LINGUACOPIER_FIXTURE,), name="CsLinguacopierLayer:IntegrationTesting"
)


CS_LINGUACOPIER_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(CS_LINGUACOPIER_FIXTURE,), name="CsLinguacopierLayer:FunctionalTesting"
)


class CsLinguacopierRestApiLayer(PloneSandboxLayer):

    defaultBases = (CS_LINGUACOPIER_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        import plone.restapi

        self.loadZCML(package=plone.restapi)

    def setUpPloneSite(self, portal):
        applyProfile(portal, "plone.restapi:default")


CS_LINGUACOPIER_RESTAPI_FIXTURE = CsLinguacopierRestApiLayer()


CS_LINGUACOPIER_RESTAPI_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(CS_LINGUACOPIER_RESTAPI_FIXTURE, zope.WSGI_SERVER_FIXTURE),
    name="CsLinguacopierRestApiLayer:FunctionalTesting",
)


CS_LINGUACOPIER_ACCEPTANCE_TESTING = FunctionalTesting(
    bases=(
        CS_LINGUACOPIER_FIXTURE,
        REMOTE_LIBRARY_BUNDLE_FIXTURE,
        zope.WSGI_SERVER_FIXTURE,
    ),
    name="CsLinguacopierLayer:AcceptanceTesting",
)


class FakeTranslationService:
    """A fake external translation service that records and marks values."""

    order = 1

    def __init__(self, skip=()):
        self.calls = []
        #: Values the service refuses to translate, to fake a partial result.
        self.skip = set(skip)

    def is_available(self):
        return True

    def available_languages(self):
        return []

    def translate_content(self, content, source_language, target_language):
        self.calls.append((content, source_language, target_language))
        if content in self.skip:
            return None
        return f"[{target_language}] {content}"
