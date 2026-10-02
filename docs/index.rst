====================
cs.linguacopier
====================

User documentation


Copying content to other languages
==================================

cs.linguacopier adds an action to copy the contents of an object (and, optionally,
its subobjects) into one or more target languages, so that translators start from
a copy of the original instead of an empty page.

It does **not** translate the content: it copies it.


Classic UI
----------

On any content object, use the **Copy language content** action to open the
``@@copy-content-to`` form. Choose one or more target languages, and whether to
include the context object and/or its subobjects.

After the copy, the form shows a report of what happened: a summary of the
created, updated, skipped, and failed items, and one row per object and language
with its status and, for failures, the reason. The report table can be exported
as CSV (which opens in Excel) with the **Export as CSV** button.


REST API
--------

When `plone.restapi <https://pypi.org/project/plone.restapi/>`_ is installed, the
same capability is available over REST, so a Volto front end can use it. The
endpoint exists only when ``plone.restapi`` is installed.

``POST /<content>/@copy-content-to``
    Copy the addressed object and/or its subobjects into the requested target
    languages. Requires the **Manage portal** permission (``cmf.ManagePortal``).

Request body
~~~~~~~~~~~~

.. code-block:: json

    {
      "target_languages": ["es"],
      "include_context": true,
      "include_children": true
    }

``target_languages``
    Required, non-empty. The language codes to copy into; each must be a
    supported content language.

``include_context``
    Optional boolean, default ``false``. Also copy the addressed object itself.

``include_children``
    Optional boolean, default ``false``. Also copy its subobjects.

At least one of ``include_context`` or ``include_children`` must be ``true``.

Response
~~~~~~~~

A handled request always answers ``200`` and reports the outcome per object:

.. code-block:: json

    {
      "@id": "http://localhost:8080/Plone/ca/folder",
      "target_languages": ["es"],
      "copied": [
        {
          "@id": "http://localhost:8080/Plone/es/folder",
          "language": "es",
          "status": "created"
        },
        {
          "@id": "http://localhost:8080/Plone/es/folder/child",
          "language": "es",
          "status": "created"
        }
      ],
      "errors": []
    }

``copied``
    One entry per object copied or intentionally skipped. ``status`` is
    ``created``, ``updated``, or ``skipped``.

``errors``
    One entry per object that could not be copied, or per validation failure.
    An item error carries the original item's ``@id``, the target ``language``,
    and a ``message``. A validation error carries the addressed object's ``@id``
    and a ``message`` (and no ``language``).

Copying is best effort: a failure on one object is reported in ``errors`` and
does not abort the rest.
