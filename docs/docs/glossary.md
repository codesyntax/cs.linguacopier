---
myst:
  html_meta:
    "description": "Terms and definitions used throughout the cs.linguacopier documentation."
    "property=og:description": "Terms and definitions used throughout the cs.linguacopier documentation."
    "property=og:title": "Glossary"
    "keywords": "Plone, documentation, glossary, term, definition, linguacopier"
---

This glossary provides terms and definitions relevant to **cs.linguacopier**.

(glossary-label)=

# Glossary

```{glossary}
:sorted: true

classic UI
    The server-rendered Plone interface. In the classic UI, the copier is reached through the **Copy language content** action, which opens the `@@copy-content-to` form.

REST API
    The JSON HTTP interface provided by `plone.restapi`. It is available only when `plone.restapi` is installed.

target language
    A language into which content is copied. The content's own language is never offered as a target.

Content copier
    The browser-agnostic `ContentCopier` class that performs a copy. Both the classic UI form and the REST endpoint call it, so their behaviour cannot drift.

copy report
    The `CopyReport` returned by `ContentCopier.copy`. It carries the successful results (`CopyResult`) and the failures (`CopyError`), and both surfaces present it to the user.

best effort
    The copier isolates each object in a `transaction.savepoint`. A failure on one object is recorded and rolled back without aborting the rest of the copy.

external translation service
    A service registered in Plone that translates a piece of text from one language to another, for example Google Translate or DeepL. `plone.app.multilingual` selects among the registered services. A copy can optionally translate the copied text with it.

translation outcome
    The per-object result of translating a copy: `translated` (every eligible field value was translated), `partial` (some were), or `not_translated` (none was). It is a note, not a failure, and is absent when translation was not requested.

language-independent field
    A field marked with `plone.app.multilingual`'s language-independent marker, whose value is the same across all translations (for example a shared relation). `plone.app.multilingual` copies and keeps such fields in sync, so the copier does not copy or translate them.

Plone
    [Plone](https://plone.org/) is an open source content management system used to create, edit, and manage digital content.
```
