# cs.linguacopier documentation

Documentation for `cs.linguacopier`, a Plone add-on to copy content between languages.

This project provides a Sphinx-based documentation environment, powered by the
[Plone Sphinx Theme](https://github.com/plone/plone-sphinx-theme).
It's generated from the `documentation_starter` template from [Cookieplone](https://github.com/plone/cookieplone).

## Prerequisites

- [uv](https://docs.astral.sh/uv/) is the recommended tool for managing Python versions and project dependencies.

To install uv, use the following command, or visit the [uv installation page](https://docs.astral.sh/uv/getting-started/installation/) for alternative methods.

```shell
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Build documentation

To build the HTML documentation, issue the following command.

```shell
make html
```

To build the HTML documentation and view a live preview while editing your documentation, issue the following command.

```shell
make livehtml
```

To check for broken links in your documentation, issue the following command.

```shell
make linkcheckbroken
```

To check spelling, grammar, and style in your documentation, issue the following command.
You should pay attention to errors and warnings, and suggestions may get noisy.

```shell
make vale
```

To delete the `docs` build directory and Python virtual environment, and reinitialize Python virtual environment, issue the following command.
This is useful to force reinstall dependencies and purge cached files in Sphinx builds.

```shell
make init
```

For more `make` commands, issue the following command.

```shell
make help
```

## Read the Docs

[Read the Docs](https://about.readthedocs.com/) provides hosting of documentation and pull request previews.

Your documentation scaffold is partially configured to use Read the Docs.
In several files, search for the string `MY_READTHEDOCS_PROJECT_SLUG`.
You'll need to replace that string with the slug that Read the Docs creates for you when you import your project.

For complete documentation of this process, see the Plone 6 Documentation [Pull request preview builds](https://6.docs.plone.org/contributing/documentation/admins.html#pull-request-preview-builds).

See also Read the Docs documentation:

- [Pull request previews](https://docs.readthedocs.com/platform/stable/pull-requests.html)
- [Build process overview](https://docs.readthedocs.com/platform/stable/builds.html)
