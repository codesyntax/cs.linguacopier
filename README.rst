|PyPI| |Python versions| |Plone versions| |Tests| |License| |GitHub issues| |GitHub last commit|

.. |PyPI| image:: https://img.shields.io/pypi/v/cs.linguacopier
   :target: https://pypi.org/project/cs.linguacopier/
   :alt: PyPI

.. |Python versions| image:: https://img.shields.io/pypi/pyversions/cs.linguacopier
   :target: https://pypi.org/project/cs.linguacopier/
   :alt: Python versions

.. |Plone versions| image:: https://img.shields.io/pypi/frameworkversions/plone/cs.linguacopier
   :target: https://pypi.org/project/cs.linguacopier/
   :alt: Plone versions

.. |Tests| image:: https://github.com/codesyntax/cs.linguacopier/actions/workflows/test-matrix.yml/badge.svg
   :target: https://github.com/codesyntax/cs.linguacopier/actions
   :alt: Tests

.. |License| image:: https://img.shields.io/pypi/l/cs.linguacopier
   :target: https://github.com/codesyntax/cs.linguacopier/blob/master/LICENSE.txt
   :alt: License

.. |GitHub issues| image:: https://img.shields.io/github/issues/codesyntax/cs.linguacopier
   :target: https://github.com/codesyntax/cs.linguacopier/issues
   :alt: GitHub issues

.. |GitHub last commit| image:: https://img.shields.io/github/last-commit/codesyntax/cs.linguacopier
   :target: https://github.com/codesyntax/cs.linguacopier/commits/master
   :alt: GitHub last commit

==============================================================================
cs.linguacopier
==============================================================================

This products adds an action to copy contents to a selected language.

We have faced many times the work to create the contents of a site in one language and then recreate
it in another language to let the customer or translators translate it.

This products provides an action with several options, which allows the content editor to recreate the contents of one section of the site in one or more languages, easing the work of the content editor.

Disclaimer: this product does not effectively translate the contents (does not translate "House" to "Casa"), it just copies the actual content in the other language

Installation
------------

Install cs.linguacopier by adding it to your buildout::

    [buildout]

    ...

    eggs =
        cs.linguacopier


and then running ``bin/buildout``


Contribute
----------

- Issue Tracker: https://github.com/codesyntax/cs.linguacopier/issues
- Source Code: https://github.com/codesyntax/cs.linguacopier
- Use case: https://erral.github.io/ploneconf2017-multi-plone/


Support
-------

If you are having issues, please let us know using the Github Issue Tracker: https://github.com/codesyntax/cs.linguacopier/issues


License
-------

The project is licensed under the GPLv2.
