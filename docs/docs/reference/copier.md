---
myst:
  html_meta:
    "description": "Reference for the cs.linguacopier Python API."
    "property=og:description": "Reference for the cs.linguacopier Python API."
    "property=og:title": "Python API reference"
    "keywords": "Plone, cs.linguacopier, Python API, ContentCopier"
---

# Python API reference

The copier is browser-agnostic and can be called directly.

## `cs.linguacopier.copier.ContentCopier`

```python
from cs.linguacopier.copier import ContentCopier
```

`ContentCopier(context)`
: Create a copier for the given content object.

`copy(target_languages, include_context=False, include_children=False, translate=False)`
: Copy the context and/or its descendants into `target_languages`, and return a `CopyReport`. When `translate` is true, text field values are translated with the configured {term}`external translation service`, keeping the original when nothing can translate it.

The copy is {term}`best effort`: each object is isolated in a `transaction.savepoint`, so a failure on one object rolls back only that object and is recorded, while the rest are copied. The copier does not commit; the caller owns the transaction.

## `cs.linguacopier.copier.CopyReport`

`successes`
: A list of `CopyResult` objects.

`errors`
: A list of `CopyError` objects.

### `CopyResult`

`target`
: The copied object. For a skipped object, the source object (there is no target).

`language`
: The target language.

`status`
: One of `created`, `updated`, or `skipped`, available as the constants `cs.linguacopier.copier.CREATED`, `UPDATED`, and `SKIPPED`.

`translation`
: The {term}`translation outcome` of the object — `translated`, `partial`, or `not_translated` — available as the constants `cs.linguacopier.copier.TRANSLATED`, `PARTIAL`, and `NOT_TRANSLATED`. It is `None` when translation was not requested.

### `CopyError`

`source`
: The original object that could not be copied.

`language`
: The target language it failed for.

`message`
: The reason for the failure.

## Translation

`copy(..., translate=True)` translates the copied text field values with the external translation service registered in `plone.app.multilingual`, keeping the original when nothing can translate it.

- Only text-bearing values are translated: scalar strings (such as the title and description) and RichText (its raw HTML is translated and rewrapped, preserving markup). String lists, non-text values, and empty values are copied verbatim.
- Fields marked language-independent (`plone.app.multilingual.dx.interfaces.ILanguageIndependentField`) are left to `plone.app.multilingual` and are not copied or translated by the copier; this keeps shared data (for example a relation) consistent across translations.
- The translation call is isolated in `cs.linguacopier.translation`, which imports the (unreleased) `plone.app.multilingual` external-translation API defensively. Without that API, or with no service configured, translation is a no-op and the copy is verbatim.

## `cs.linguacopier.languages`

The rule for which languages a copy can target.

`current_language(context)`
: The context's language code, or `None` when it has none.

`target_language_vocabulary(context)`
: The supported content languages, minus the context's own language.

`has_target_languages(context)`
: Whether there is any language other than the context's own to copy to.

## Extending the copier

Register an `ITranslateThings` multi-adapter for the pair of `(original, translated)` objects. Its `translate()` method is called while copying, from both the classic UI form and the REST endpoint.

```python
from cs.linguacopier.interfaces import ITranslateThings
from zope.interface import implementer


@implementer(ITranslateThings)
class MyTranslator:
    def __init__(self, original, translated):
        self.original = original
        self.translated = translated

    def translate(self):
        self.translated.custom_field = self.original.custom_field
```
