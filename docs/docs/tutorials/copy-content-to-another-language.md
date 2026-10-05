---
myst:
  html_meta:
    "description": "Copy content to another language in Plone."
    "property=og:description": "Copy content to another language in Plone."
    "property=og:title": "Copy content to another language"
    "keywords": "Plone, cs.linguacopier, tutorial, copy, translation"
---

# Copy content to another language

In this tutorial you will copy a section of a Plone site into a second language, so that a translator starts from a copy of the original content instead of an empty page.

## Prerequisites

- A Plone site with at least two {term}`target language`s configured, and `plone.app.multilingual` installed.
- `cs.linguacopier` installed.
- A user with the **Manage portal** permission.

## Create the source content

1.  In the {term}`classic UI`, create a folder in the default language and add a couple of pages inside it.

    Each page inherits the language of the language root folder it lives in.

## Copy the section

1.  Open the folder you created.

1.  From the toolbar, choose {guilabel}`Copy language content`.

    The `@@copy-content-to` form opens.

1.  Select one or more {term}`target language`s.

    The content's own language is not listed.

1.  Leave {guilabel}`Include context element?` and {guilabel}`Include the contents?` checked to copy the folder and every page inside it.

1.  Optionally tick {guilabel}`Translate the copied content?` to translate the text with the {term}`external translation service` configured in the site, so the copy is a draft in the target language instead of the original wording.

    The original value is kept when nothing can translate it.

1.  Choose {guilabel}`Copy content`.

## Read the {term}`copy report`

The form re-renders with a report of what happened.

- A summary line counts the copied items by status: *created*, *updated*, *skipped*, and *failed*.
- A table lists one row per object and language, with its status and, for failures, the reason.
- When translation was requested, the table also shows the {term}`translation outcome` of each object (*Translated*, *Partial*, or *Not translated*).

You can download the table as a CSV file, which opens in a spreadsheet application such as Excel, with the {guilabel}`Export as CSV` button.

## Check the result

1.  Switch to one of the target languages.

    The folder and its pages are there, copied from the original, ready for a translator to edit.
