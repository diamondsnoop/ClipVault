# Creator Registry Program Logs

Creator registry commands should make local state changes explicit.

Use these prefixes:

- `[creator] added: <name> (<platform>)` — a new source was recorded.
- `[creator] updated: <name> (<platform>)` — an existing source URL was updated.
- `[creator] listed: <count>` — records were listed.
- `[creator] fetching: <name> (<platform>)` — a recorded source is being used
  for recent-entry discovery.
- `[creator] fetching recent entries from <url>` — `yt-dlp` flat extraction is
  starting for a source URL.
- `[creator] discovered: <count>` — recent-entry discovery completed.
- `[creator] candidates: <new> new, <processed> processed` — discovered
  entries were compared with completed local manifests.
- `[creator] processed lookup: indexes` — processed status was read from
  creator `_index.json` files.
- `[creator] processed lookup: manifests` — processed status fell back to a
  manifest scan because no creator indexes were available.
- `[creator] index lookup skipped (<path>): <reason>` — one index file could
  not be used for processed-status lookup.
- `[creator] registry: <path>` — registry file path after a write.
- `[creator] registry load failed (<path>): <reason>` — registry JSON could not
  be read.
- `[creator] invalid registry shape (<path>), starting empty` — registry file
  exists but does not match the expected shape.
- `[queue] added: <count>, skipped processed: <count>, skipped existing: <count>`
  — new creator entries were written to the local job queue.
- `[queue] path: <path>` — queue file path after a write.
- `[queue] load failed (<path>): <reason>` — queue JSON could not be read.
- `[queue] invalid queue shape (<path>), starting empty` — queue file exists
  but does not match the expected shape.
- `[queue] listed: <count>` — queued jobs were listed.
- `[queue] status: <counts>` — queue status summary was reported.
- `[queue] running: <count>` — queue execution selected jobs to run.
- `[queue] job start: <id> <url>` — one queued video is starting.
- `[queue] job done: <id>` — one queued video finished successfully.
- `[queue] job failed: <id> <reason>` — one queued video failed and was
  recorded in `_queue.json`.

Creator registry failures should be understandable from the command output.
Unknown platforms should fail clearly instead of creating ambiguous records.
