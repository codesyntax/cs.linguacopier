.. image:: https://secure.travis-ci.org/codesyntax/cs.linguacopier.png?branch=master
 :target: http://travis-ci.org/codesyntax/cs.linguacopier

.. image:: https://coveralls.io/repos/github/codesyntax/cs.linguacopier/badge.svg?branch=master
 :target: https://coveralls.io/github/codesyntax/cs.linguacopier?branch=master

.. image:: https://landscape.io/github/codesyntax/cs.linguacopier/master/landscape.svg?style=flat
  :target: https://landscape.io/github/codesyntax/cs.linguacopier/master
  :alt: Code Health

.. image:: https://readthedocs.org/projects/cslinguacopier/badge/?version=latest
  :target: https://cslinguacopier.readthedocs.io/en/latest/?badge=latest

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
