When a copy translates content, the copied object's id (its URL segment) is now
derived from its translated title, normalized with the target language's rules,
so a translated page has a URL in the target language instead of the original
wording. It applies only when a translation is first created, keeps the default
id when the title is empty, and makes colliding ids unique the Plone way.
