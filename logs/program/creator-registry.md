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
- `[creator] registry: <path>` — registry file path after a write.
- `[creator] registry load failed (<path>): <reason>` — registry JSON could not
  be read.
- `[creator] invalid registry shape (<path>), starting empty` — registry file
  exists but does not match the expected shape.

Creator registry failures should be understandable from the command output.
Unknown platforms should fail clearly instead of creating ambiguous records.
