Add a ``translate`` option to the content copier: a checkbox in the
``@@copy-content-to`` form and a ``translate`` boolean on the
``@copy-content-to`` REST request. When set, the copied text field values are
translated with the external translation service configured in Plone, keeping
the original value when nothing can translate it. Fields marked as
language-independent are left to plone.app.multilingual, which shares and keeps
them in sync, so the copier does not copy them. The copy report shows which
items were translated in full, in part, or not at all.
