Add a ``translate`` option to the content copier: a checkbox in the
``@@copy-content-to`` form and a ``translate`` boolean on the
``@copy-content-to`` REST request. When set, the copied text field values are
translated with the external translation service configured in Plone, keeping
the original value when nothing can translate it. Fields marked as
language-independent are copied but not translated.
