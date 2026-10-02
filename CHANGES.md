# Changelog

<!--
   You should *NOT* be adding new change log entries to this file.
   You should create a file in the news directory instead.
   For helpful instructions, please see:
   https://github.com/plone/plone.releaser/blob/master/ADD-A-NEWS-ITEM.rst
-->

<!-- towncrier release notes start -->

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
