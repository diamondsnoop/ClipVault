# Index Maintenance Program Logs

Index maintenance commands should make local filesystem work visible without
being noisy.

Use these prefixes for index rebuild and related maintenance features:

- `[library] scanning: <path>` — starting a local library scan.
- `[index] rebuilt creator: <path>` — creator `_index.json` was written.
- `[index] rebuilt series: <path>` — series `_index.json` was written.
- `[index] skipped manifest (<path>): <reason>` — a manifest was ignored but
  the rebuild continued.
- `[index] removed stale: <path>` — an index no longer backed by manifests was
  deleted.
- `[index] failed removing stale (<path>): <reason>` — stale cleanup failed but
  the rebuild continued.
- `[index] dry-run: ...` — a maintenance command reported planned writes
  without modifying files.

Maintenance commands must not hide failures silently. If an error is
non-blocking, log the skipped operation and enough path context for a bug
report.
