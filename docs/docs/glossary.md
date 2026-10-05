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

copy job
    A copy queued to run in the background instead of inside the request. It is stored in the ZODB with its parameters, status, progress and errors, and is executed by the {term}`background worker`.

background worker
    The external command that processes queued {term}`copy job`s. It runs against the same database as the site, is scheduled with cron or a systemd timer, and writes a heartbeat the control panel reads.

Plone
    [Plone](https://plone.org/) is an open source content management system used to create, edit, and manage digital content.
```
