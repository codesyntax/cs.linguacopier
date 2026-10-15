from . import logger


def upgrade(setup_tool=None):
    """Install the copier's Site Setup panels and their settings records.

    Sites already at profile version 1001 predate the panels, so re-import the
    ``controlpanel`` step to register the configlets and the
    ``plone.app.registry`` step to create the settings records.
    """
    logger.info("Running upgrade (Python): register the content copier panels")
    setup_tool.runImportStepFromProfile("cs.linguacopier:default", "controlpanel")
    setup_tool.runImportStepFromProfile("cs.linguacopier:default", "plone.app.registry")
