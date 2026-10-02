"""REST service exposing the content copier to Volto.

``POST /<content>/@copy-content-to`` copies the addressed object and/or its
subtree into the requested target languages, mirroring the ``@@copy-content-to``
form.
"""

from cs.linguacopier.copier import ContentCopier
from cs.linguacopier.languages import current_language
from cs.linguacopier.languages import target_language_vocabulary
from plone.protect.interfaces import IDisableCSRFProtection
from plone.restapi.deserializer import json_body
from plone.restapi.services import Service
from zope.interface import alsoProvides


class CopyContentToLanguage(Service):
    def reply(self):
        alsoProvides(self.request, IDisableCSRFProtection)

        data = json_body(self.request)
        target_languages = data.get("target_languages") or []
        include_context = bool(data.get("include_context", False))
        include_children = bool(data.get("include_children", False))
        translate = bool(data.get("translate", False))

        errors = self._validate(target_languages, include_context, include_children)
        copied = []
        if not errors:
            report = ContentCopier(self.context).copy(
                target_languages,
                include_context=include_context,
                include_children=include_children,
                translate=translate,
            )
            copied = [
                {
                    "@id": result.target.absolute_url(),
                    "language": result.language,
                    "status": result.status,
                }
                for result in report.successes
            ]
            errors = [
                {
                    "@id": error.source.absolute_url(),
                    "language": error.language,
                    "message": error.message,
                }
                for error in report.errors
            ]

        return {
            "@id": self.context.absolute_url(),
            "target_languages": target_languages,
            "copied": copied,
            "errors": errors,
        }

    def _validate(self, target_languages, include_context, include_children):
        """Return request-level validation errors (context URL, no language)."""
        if not target_languages:
            return [
                {
                    "@id": self.context.absolute_url(),
                    "message": "target_languages must not be empty",
                }
            ]

        errors = []
        available = {term.value for term in target_language_vocabulary(self.context)}
        current = current_language(self.context)
        for language in target_languages:
            if language in available:
                continue
            if language == current:
                message = f"Cannot copy to the content's own language: {language}"
            else:
                message = f"Unsupported language: {language}"
            errors.append(
                {
                    "@id": self.context.absolute_url(),
                    "message": message,
                }
            )
        if not (include_context or include_children):
            errors.append(
                {
                    "@id": self.context.absolute_url(),
                    "message": "Set include_context and/or include_children",
                }
            )
        return errors
