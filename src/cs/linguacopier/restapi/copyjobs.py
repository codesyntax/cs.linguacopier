"""REST service exposing background copy jobs.

``GET /<content>/@copy-jobs`` lists the jobs; ``GET /<content>/@copy-jobs/<id>``
returns one job's status, progress, parameters and bounded errors.
"""

from cs.linguacopier.interfaces import ICopyJobQueue
from plone.restapi.services import Service
from zope.component import getUtility
from zope.interface import implementer
from zope.publisher.interfaces import IPublishTraverse


@implementer(IPublishTraverse)
class CopyJobsGet(Service):
    def __init__(self, context, request):
        super().__init__(context, request)
        self.params = []

    def publishTraverse(self, request, name):
        # Treat any path segment after /@copy-jobs as the job id.
        self.params.append(name)
        return self

    def reply(self):
        queue = getUtility(ICopyJobQueue)
        if self.params:
            job = queue.get(self.params[0])
            if job is None:
                self.request.response.setStatus(404)
                return {
                    "error": {
                        "type": "Not Found",
                        "message": f"No such job: {self.params[0]}",
                    }
                }
            return job.to_dict()
        return {"jobs": [job.to_dict() for job in queue.all()]}
