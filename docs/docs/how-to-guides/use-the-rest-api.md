---
myst:
  html_meta:
    "description": "Use the cs.linguacopier REST API to copy content between languages."
    "property=og:description": "Use the cs.linguacopier REST API to copy content between languages."
    "property=og:title": "Use the REST API"
    "keywords": "Plone, cs.linguacopier, REST API, plone.restapi, Volto"
---

# Use the REST API

This guide shows how to copy content to other languages over the {term}`REST API`, for example from a Volto front end.

## Prerequisites

- `plone.restapi` installed on the site.

    The endpoint exists only when `plone.restapi` is installed.

- A user with the **Manage portal** permission.

## Call the endpoint

Send a `POST` request to the `@copy-content-to` endpoint of the object you want to copy.

```http
POST /Plone/ca/folder/@copy-content-to HTTP/1.1
Accept: application/json
Content-Type: application/json

{
  "target_languages": ["es"],
  "include_context": true,
  "include_children": true,
  "translate": true
}
```

The request body has the following fields.

`target_languages`
: Required, non-empty. The language codes to copy into. Each must be a supported content language other than the addressed content's own language.

`include_context`
: Optional boolean, default `false`. Also copy the addressed object itself.

`include_children`
: Optional boolean, default `false`. Also copy its subobjects.

`translate`
: Optional boolean, default `false`. Translate the copied text fields with the {term}`external translation service` configured in the site, instead of copying them verbatim. The original is kept when nothing can translate it.

At least one of `include_context` or `include_children` must be `true`.

## Read the response

A handled request always answers `200` with a per-object result.

```json
{
  "@id": "http://localhost:8080/Plone/ca/folder",
  "target_languages": ["es"],
  "copied": [
    {
      "@id": "http://localhost:8080/Plone/es/folder",
      "language": "es",
      "status": "created",
      "translation": "translated"
    },
    {
      "@id": "http://localhost:8080/Plone/es/folder/child",
      "language": "es",
      "status": "created",
      "translation": "translated"
    }
  ],
  "errors": []
}
```

`copied`
: One entry per object copied or intentionally skipped. `status` is `created`, `updated`, or `skipped`. When translation was requested, each entry also carries a `translation` field with the {term}`translation outcome` (`translated`, `partial`, or `not_translated`).

`errors`
: One entry per object that could not be copied, or per validation failure. An item error carries the original item's `@id`, the target `language`, and a `message`. A validation error carries the addressed object's `@id` and a `message` (and no `language`).

Copying is best effort: a failure on one object is reported in `errors` and does not abort the rest.
