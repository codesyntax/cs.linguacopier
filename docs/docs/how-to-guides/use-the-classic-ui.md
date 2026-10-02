---
myst:
  html_meta:
    "description": "Use the cs.linguacopier form in the Plone classic UI."
    "property=og:description": "Use the cs.linguacopier form in the Plone classic UI."
    "property=og:title": "Use the classic UI form"
    "keywords": "Plone, cs.linguacopier, classic UI, form, copy"
---

# Use the classic UI form

This guide shows how to copy content to other languages with the `@@copy-content-to` form.

## Install the add-on

Add `cs.linguacopier` to your project's dependencies, then install the **cs.linguacopier** add-on from the Add-ons control panel.

## Copy content

1.  Open the content object you want to copy.

1.  From the toolbar, choose {guilabel}`Copy language content`.

    The form opens. The {guilabel}`Target languages` list contains the supported languages of the site, except the content's own language.

1.  Select one or more {term}`target language`s.

1.  Optionally uncheck {guilabel}`Include context element?` to copy only the subobjects, or {guilabel}`Include the contents?` to copy only the object itself.

    At least one of the two must be selected.

1.  Choose {guilabel}`Copy content`.

```{note}
If the site has no other language configured, the form is hidden and a note is shown instead, because there is nothing to copy to.
```

## Read the {term}`copy report`

After the copy, the form shows a report of the outcome.

- A summary counts the items by status: *created*, *updated*, *skipped*, and *failed*.
- A table lists one row per object and language, with its status and, for failures, the reason.

Items are *skipped* when their content type is configured not to be copied, for example a language-independent `LIF` folder. Skipping is not an error.

Choose {guilabel}`Export as CSV` to download the report table as a CSV file that opens in a spreadsheet application such as Excel.

```{note}
A failure on one object does not abort the copy: the remaining objects are still copied, and every failure is listed in the report.
```
