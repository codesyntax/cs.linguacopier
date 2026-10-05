"""REST service exposing background copy jobs.

``GET /<content>/@copy-jobs`` lists the jobs; ``GET /<content>/@copy-jobs/<id>``
returns one job's status, progress, parameters and bounded errors; ``DELETE
/<content>/@copy-jobs/<id>`` cancels a job.
"""

from cs.linguacopier.interfaces import ICopyJobQueue
from plone.restapi.services import Service
from zope.component import getUtility
from zope.interface import implementer
from zope.publisher.interfaces import IPublishTraverse


@implementer(IPublishTraverse)
class _CopyJobService(Service):
    def __init__(self, context, request):
        super().__init__(context, request)
        self.params = []

    def publishTraverse(self, request, name):
        # Treat any path segment after /@copy-jobs as the job id.
        self.params.append(name)
        return self

    def _error(self, status, type, message):
        self.request.response.setStatus(status)
        return {"error": {"type": type, "message": message}}


class CopyJobsGet(_CopyJobService):
    def reply(self):
        queue = getUtility(ICopyJobQueue)
        if self.params:
            job = queue.get(self.params[0])
            if job is None:
                return self._error(404, "Not Found", f"No such job: {self.params[0]}")
            return job.to_dict()
        return {"jobs": [job.to_dict() for job in queue.all()]}


class CopyJobsDelete(_CopyJobService):
    def reply(self):
        if len(self.params) != 1:
            return self._error(400, "Bad Request", "Supply exactly one job id")
        job = getUtility(ICopyJobQueue).cancel(self.params[0])
        if job is None:
            return self._error(404, "Not Found", f"No such job: {self.params[0]}")
        return job.to_dict()
