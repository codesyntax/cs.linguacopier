---
myst:
  html_meta:
    "description": "Reference for the cs.linguacopier @copy-content-to REST endpoint."
    "property=og:description": "Reference for the cs.linguacopier @copy-content-to REST endpoint."
    "property=og:title": "REST API reference"
    "keywords": "Plone, cs.linguacopier, REST API, reference"
---

# REST API reference

The endpoint exists only when `plone.restapi` is installed. It is registered by
`cs.linguacopier.restapi`, which is included only under that condition, so the
core package never imports `plone.restapi`.

## `POST /<content>/@copy-content-to`

Copy the addressed object and/or its subobjects into the requested target languages.

| | |
| --- | --- |
| Method | `POST` |
| URL | `<content>/@copy-content-to` |
| Permission | `cmf.ManagePortal` (Manage portal) |
| CSRF | Exempt (the write opts out of `plone.protect`) |

### Request body

```json
{
  "target_languages": ["es", "ca"],
  "include_context": false,
  "include_children": false,
  "translate": false
}
```

- `target_languages` (`list` of language codes, required): the languages to copy into. Must be non-empty, each a supported content language, and none may be the addressed content's own language.
- `include_context` (`boolean`, default `false`): also copy the addressed object.
- `include_children` (`boolean`, default `false`): also copy its subobjects.
- `translate` (`boolean`, default `false`): translate the copied text fields with the configured {term}`external translation service` instead of copying them verbatim. The original is kept when nothing can translate it.

At least one of `include_context` or `include_children` must be `true`.

### Response

Every handled request returns `200`.

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
    }
  ],
  "errors": []
}
```

- `@id` (`string`): the addressed object's URL.
- `target_languages` (`list`): echoed back from the request.
- `copied` (`list`): one entry per object copied or intentionally skipped, with `@id` (target), `language`, and `status` (`created`, `updated`, or `skipped`). When translation was requested, the entry also carries `translation`, the {term}`translation outcome` (`translated`, `partial`, or `not_translated`).
- `errors` (`list`): one entry per object that could not be copied, or per validation failure. An item error carries `@id` (source), `language`, and `message`. A validation error carries `@id` (the addressed context) and `message`, and no `language`.

Malformed JSON is rejected by `plone.restapi` before the service runs.
