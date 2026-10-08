# Changelog

<!--
   You should *NOT* be adding new change log entries to this file.
   You should create a file in the news directory instead.
   For helpful instructions, please see:
   https://github.com/plone/plone.releaser/blob/master/ADD-A-NEWS-ITEM.rst
-->

<!-- towncrier release notes start -->

## 2.2 (2026-10-08)


### New features

- When a copy translates content, the copied object's id (its URL segment) is now
  derived from its translated title, normalized with the target language's rules,
  so a translated page has a URL in the target language instead of the original
  wording. It applies only when a translation is first created, keeps the default
  id when the title is empty, and makes colliding ids unique the Plone way. 


### Bug fixes

- A copied subtree now keeps the source's sibling order. The copier enumerates each
  folder's direct children in their position order and, once the copy is done, sets
  each target folder's order to match its source, so a translated section reads in
  the same sequence as the original (including nested folders and existing
  translations). 
- Stop translating fields whose value is a controlled token — a vocabulary term, a
  taxonomy value, or any other enumerated value. Such fields are now copied
  verbatim, so a translated copy never stores an invalid value that can break the
  page that renders it; free text is still translated. 

## 2.1 (2026-10-05)


### New features

- Add a ``translate`` option to the content copier: a checkbox in the
  ``@@copy-content-to`` form and a ``translate`` boolean on the
  ``@copy-content-to`` REST request. When set, the copied text field values are
  translated with the external translation service configured in Plone, keeping
  the original value when nothing can translate it. Fields marked as
  language-independent are left to plone.app.multilingual, which shares and keeps
  them in sync, so the copier does not copy them. The copy report shows which
  items were translated in full, in part, or not at all. 


### Documentation

- Document the optional translation of copied content: the translate option in the
  classic UI form and the REST API, the three-valued translation outcome in the copy
  report, the field selection and fallbacks, and the external translation service it
  relies on. 

## 2.0 (2026-10-02)


### Breaking changes

- Replace ``pkg_resources`` namespace with PEP 420 native namespace.
  Support only Plone 6.2 and Python 3.10+. #3928
- Rename the ``@@copy-content-to`` form fields to ``include_context`` and
  ``include_children``, matching the new REST API parameter names. 


### New features

- Add a ``POST /<content>/@copy-content-to`` REST service so that a Volto front end
  can copy content and its subobjects into target languages. The endpoint is
  available when ``plone.restapi`` is installed. 
- Show the outcome of a copy in the classic-UI ``@@copy-content-to`` form: a
  per-object report (created, updated, skipped, failed) with the reasons for the
  failures, exportable as CSV. 
- Stop offering the content's own language as a copy target: the
  ``@@copy-content-to`` form lists only the other supported languages (and is
  hidden when there is none), and the REST endpoint rejects a request that names
  the content's own language. 


### Bug fixes

- Fix ``copy_other_things`` adapter lookup and updating of existing
  properties in ``copy_other_properties``. 


### Internal

- Update configuration files @plone 


### Tests

- Add unit and integration tests for the content copier. 

## 1.3 (2025-08-28)


### Internal

- Repackage @erral


## 1.2 (2024-07-23)

- Remove includeDependencies for Plone 6 compatibility. @erral


## 1.1 (2021-03-22)

- add my name @libargutxi
- RelationList @libargutxi
- RelationList fields @libargutxi

## 1.0 (2019-07-11)

- Initial release. @erral
