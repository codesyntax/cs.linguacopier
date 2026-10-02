"""Installer for the cs.linguacopier package."""

from setuptools import setup

long_description = "\n\n".join(
    [
        open("README.md").read(),
        open("CHANGES.md").read(),
    ]
)


setup(
    name="cs.linguacopier",
    version="2.0",
    description="Content-copier useful to copy basic content from one language-tree to another to start working with the whole content-tree",
    long_description=long_description,
    long_description_content_type="text/markdown",
    # Get more from https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        "Environment :: Web Environment",
        "Framework :: Plone",
        "Framework :: Plone :: 6.2",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
        "Operating System :: OS Independent",
        "Development Status :: 5 - Production/Stable",
    ],
    keywords="Python Plone",
    author="Mikel Larreategi",
    author_email="mlarreategi@codesyntax.com",
    url="https://pypi.python.org/pypi/cs.linguacopier",
    license="GPL version 2",
    include_package_data=True,
    python_requires=">3.9,<3.15",
    zip_safe=False,
    install_requires=[
        "plone.api",
        "plone.base",
        "plone.app.multilingual",
        "plone.app.textfield",
        "plone.app.z3cform",
        "plone.behavior",
        "plone.dexterity",
        "plone.protect",
        "plone.uuid",
        "Products.GenericSetup>=1.8.2",
        "z3c.form",
        "z3c.relationfield",
        "zope.intid",
        "Zope",
    ],
    extras_require={
        "test": [
            "plone.app.testing",
            # Plone KGS does not use this version, because it would break
            # Remove if your package shall be part of coredev.
            # plone_coredev tests as of 2016-04-01.
            "plone.testing",
            "plone.app.contenttypes",
            "plone.app.robotframework[debug]",
            "plone.browserlayer",
            "Products.statusmessages",
            "plone.app.relationfield",
            "plone.restapi",
            "requests",
        ],
    },
    entry_points="""
    [z3c.autoinclude.plugin]
    target = plone
    """,
)
