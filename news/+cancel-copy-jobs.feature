Background copy jobs are now processed in chunks, so a large copy commits its
progress progressively instead of in one transaction, and a job interrupted by a
worker restart resumes where it stopped. A job can be cancelled with ``DELETE
@copy-jobs/<id>``: a queued job stops at once, a running one at the next chunk
boundary.