---
myst:
  html_meta:
    "description": "Run the cs.linguacopier background worker to process queued copy jobs."
    "property=og:description": "Run the cs.linguacopier background worker to process queued copy jobs."
    "property=og:title": "Run the background worker"
    "keywords": "Plone, cs.linguacopier, background, worker, cron, systemd, retention"
---

# Run the background worker

A large translated copy can take a long time, so `cs.linguacopier` can run it as
a background {term}`copy job` instead of inside the request. A copy is queued as
a job when

- the copy is sent with `mode` set to `background` (from the classic UI form or
  the {term}`REST API`), or
- the {term}`content copier` decides the copy is big enough to defer (the
  automatic mode).

Queued jobs are processed by a **worker** that you run as a separate command
against the same database. The worker is intentionally a plain external command:
there is no message broker, no in-process thread, and no clock server to
configure.

## Run the worker once

Run the worker once for every Plone site in the instance:

```bash
bin/instance run src/cs/linguacopier/worker.py
```

The command drains the queued jobs, oldest first, copying each in chunks and
committing as it goes. Running it by hand is enough to work through a backlog.

## Schedule the worker

Run the command on a schedule so queued jobs are picked up automatically.

### cron

```cron
*/5 * * * * cd /path/to/instance && bin/instance run src/cs/linguacopier/worker.py
```

### systemd

```ini
# /etc/systemd/system/linguacopier-worker.service
[Unit]
Description=cs.linguacopier background copy worker

[Service]
Type=oneshot
WorkingDirectory=/path/to/instance
ExecStart=/path/to/instance/bin/instance run src/cs/linguacopier/worker.py
```

```ini
# /etc/systemd/system/linguacopier-worker.timer
[Unit]
Description=Run the cs.linguacopier worker every five minutes

[Timer]
OnBootSec=1min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
```

Enable it with:

```bash
systemctl enable --now linguacopier-worker.timer
```

## Watch progress and health

Every run writes a **heartbeat** that the **Copy jobs** panel
(`@@linguacopier-jobs`, under Site Setup → Content copier) reads. If no worker
has run recently, the panel shows a warning, so you can tell a stalled queue from
an empty one. The panel also lists every job with its status, progress and
errors, and lets you cancel, retry or delete a job.

## Configure worker behaviour

All of this is in Site Setup → Content copier → **Content copier settings**:

| Setting | Meaning |
| --- | --- |
| Default copy mode | Which mode the automatic choice uses when none is given: automatic, directly or in the background. |
| Direct copy size limit | In automatic mode, the work (`objects × target languages`) at or below which a copy runs directly. |
| Background chunk size | How many items the worker copies between commits. |
| Maximum retries | How many times a chunk is retried before the job is marked failed. |
| Worker user | The user the worker acts as; leave empty to run as the site owner. |
| Job retention (days) | Finished jobs older than this are pruned by the worker. |
| Maximum stored jobs | Finished jobs beyond this many are pruned by the worker. |

The worker prunes finished, cancelled and failed jobs according to the retention
settings on every run; queued and running jobs are never pruned.
