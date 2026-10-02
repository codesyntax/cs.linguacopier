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

`copy(target_languages, include_context=False, include_children=False)`
: Copy the context and/or its descendants into `target_languages`, and return a `CopyReport`.

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

### `CopyError`

`source`
: The original object that could not be copied.

`language`
: The target language it failed for.

`message`
: The reason for the failure.

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
