# cs.linguacopier

[![PyPI](https://img.shields.io/pypi/v/cs.linguacopier)](https://pypi.org/project/cs.linguacopier/)
[![Python versions](https://img.shields.io/pypi/pyversions/cs.linguacopier)](https://pypi.org/project/cs.linguacopier/)
[![Plone versions](https://img.shields.io/pypi/frameworkversions/plone/cs.linguacopier)](https://pypi.org/project/cs.linguacopier/)
[![Tests](https://github.com/codesyntax/cs.linguacopier/actions/workflows/test-matrix.yml/badge.svg)](https://github.com/codesyntax/cs.linguacopier/actions)
[![License](https://img.shields.io/pypi/l/cs.linguacopier)](https://github.com/codesyntax/cs.linguacopier/blob/master/LICENSE.txt)
[![GitHub issues](https://img.shields.io/github/issues/codesyntax/cs.linguacopier)](https://github.com/codesyntax/cs.linguacopier/issues)
[![GitHub last commit](https://img.shields.io/github/last-commit/codesyntax/cs.linguacopier)](https://github.com/codesyntax/cs.linguacopier/commits/master)

[Full Documentation](https://codesyntax.github.io/cs.linguacopier/)

This products adds an action to copy contents to a selected language.

We have faced many times the work to create the contents of a site in one language and then recreate
it in another language to let the customer or translators translate it.

This products provides an action with several options, which allows the content editor to recreate the contents of one section of the site in one or more languages, easing the work of the content editor.

Disclaimer: this product does not effectively translate the contents (does not translate "House" to "Casa"), it just copies the actual content in the other language.

## Installation

Install cs.linguacopier by adding `cs.linguacopier` it to your project's dependencies (either buildout, pyproject.toml, requirements.txt, uv or whatever you use to manage your Plone project's dependencies).

## REST API

When [`plone.restapi`](https://pypi.org/project/plone.restapi/) is installed, the copier is also available over REST, so a Volto front end can use it:

```
POST /<content>/@copy-content-to
```

with a JSON body such as:

```json
{
  "target_languages": ["es", "ca"],
  "include_context": true,
  "include_children": true
}
```

The endpoint requires the **Manage portal** permission and always answers `200` with a per-object result. See the [documentation](https://codesyntax.github.io/cs.linguacopier/) for the full request and response contract.

## Contribute

- [Issue tracker](https://github.com/codesyntax/cs.linguacopier/issues)
- [Source code](https://github.com/codesyntax/cs.linguacopier)
- [Use case](https://erral.github.io/ploneconf2017-multi-plone/)

## Support

If you are having issues, please let us know using the Github Issue Tracker: https://github.com/codesyntax/cs.linguacopier/issues

## License

The project is licensed under the GPLv2.

## Contributors

- Mikel Larreategi, mlarreategi@codesyntax.com
