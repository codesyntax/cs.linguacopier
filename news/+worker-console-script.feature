A ``linguacopier-worker`` console script now runs the background job runner from
the instance's ``zope.conf``, so it can be scheduled by command name without
knowing where the package is installed (drained by ``linguacopier-worker
/path/to/etc/zope.conf``, which suits containers and cron).
