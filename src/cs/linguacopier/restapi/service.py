"""REST service exposing the content copier to Volto.

``POST /<content>/@copy-content-to`` copies the addressed object and/or its
subtree into the requested target languages, mirroring the ``@@copy-content-to``
form.
"""

from cs.linguacopier.copier import ContentCopier
from cs.linguacopier.interfaces import ICopyJobQueue
from cs.linguacopier.languages import current_language
from cs.linguacopier.languages import target_language_vocabulary
from cs.linguacopier.planner import BACKGROUND
from cs.linguacopier.planner import MODES
from cs.linguacopier.planner import plan
from plone import api
from plone.protect.interfaces import IDisableCSRFProtection
from plone.restapi.deserializer import json_body
from plone.restapi.services import Service
from zope.component import getUtility
from zope.interface import alsoProvides


class CopyContentToLanguage(Service):
    def reply(self):
        alsoProvides(self.request, IDisableCSRFProtection)

        data = json_body(self.request)
        target_languages = data.get("target_languages") or []
        include_context = bool(data.get("include_context", False))
        include_children = bool(data.get("include_children", False))
        translate = bool(data.get("translate", False))
        raw_mode = data.get("mode")

        errors = self._validate(
            target_languages, include_context, include_children, raw_mode
        )
        copied = []
        if not errors:
            execution = plan(
                self.context,
                raw_mode,
                target_languages,
                include_context=include_context,
                include_children=include_children,
                translate=translate,
            )
            if execution == BACKGROUND:
                job = self._enqueue(
                    target_languages, include_context, include_children, translate
                )
                self.request.response.setStatus(202)
                return {
                    "@id": self.context.absolute_url(),
                    "job": job.to_dict(),
                }
            report = ContentCopier(self.context).copy(
                target_languages,
                include_context=include_context,
                include_children=include_children,
                translate=translate,
            )
            copied = []
            for result in report.successes:
                item = {
                    "@id": result.target.absolute_url(),
                    "language": result.language,
                    "status": result.status,
                }
                if result.translation:
                    item["translation"] = result.translation
                copied.append(item)
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

    def _enqueue(self, target_languages, include_context, include_children, translate):
        params = {
            "context_path": list(self.context.getPhysicalPath()),
            "target_languages": target_languages,
            "include_context": include_context,
            "include_children": include_children,
            "translate": translate,
        }
        requested_by = api.user.get_current().getId()
        return getUtility(ICopyJobQueue).add(params, requested_by=requested_by)

    def _validate(self, target_languages, include_context, include_children, mode):
        """Return request-level validation errors (context URL, no language)."""
        if not target_languages:
            return [
                {
                    "@id": self.context.absolute_url(),
                    "message": "target_languages must not be empty",
                }
            ]

        if mode is not None and mode not in MODES:
            return [
                {
                    "@id": self.context.absolute_url(),
                    "message": f"Unsupported mode: {mode}",
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
