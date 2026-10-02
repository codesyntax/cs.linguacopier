---
myst:
  html_meta:
    "description": "How cs.linguacopier is structured."
    "property=og:description": "How cs.linguacopier is structured."
    "property=og:title": "Architecture"
    "keywords": "Plone, cs.linguacopier, architecture, ContentCopier"
---

# Architecture

`cs.linguacopier` has a single {term}`Content copier` shared by two surfaces: the {term}`classic UI` form and the {term}`REST API` endpoint.

## One pipeline, two surfaces

The {term}`Content copier`, `ContentCopier`, is a browser-agnostic class. It does not depend on `z3c.form`, on a request, or on the browser layer.

- The `@@copy-content-to` form in the classic UI is a thin delegator. It reads the submitted options, calls the copier, and renders the {term}`copy report`.
- The `@copy-content-to` REST endpoint is equally thin. It parses the JSON body, validates it, calls the same copier, and serializes the same report.

Because both surfaces call one implementation, their behaviour cannot drift, and an extension registered as an `ITranslateThings` adapter runs for both.

## Best effort

Copying a subtree can touch many objects. The copier isolates each object in its own `transaction.savepoint`.

- A failure on one object rolls back only that object, is recorded in the report, and does not abort the rest.
- The copier never commits. The request owns the transaction, and the Zope publisher commits it once at the end. This keeps a REST request a single, retry-safe transaction.

## Which languages

The content's own language is never offered as a {term}`target language`, and the REST endpoint rejects a request that names it. A copy into another language creates the translation if it is missing, or updates it if it already exists.

The rule lives in one place — `cs.linguacopier.languages` — and is used by the form's vocabulary, by the form's "nothing to copy to" guard, and by the REST endpoint's validation.

## Extending the copier

Developer extensions are registered as `ITranslateThings` multi-adapters on the pair of `(original, translated)` objects. The copier calls each adapter's `translate()` method while copying, so custom content types, annotations, or fields are handled without changing `cs.linguacopier` itself.
