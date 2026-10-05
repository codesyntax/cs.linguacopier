Add a background mode to the content copier for large translated copies. A copy
request with ``mode=background`` on ``@copy-content-to`` is stored as a
persistent job and returns ``202 Accepted`` with the job, instead of running
inside the request. A separate worker command drains the queued jobs and records
each job's status, progress and errors; ``GET @copy-jobs`` lists the jobs and
``GET @copy-jobs/<id>`` reports one.