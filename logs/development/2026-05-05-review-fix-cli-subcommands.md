# 2026-05-05: Review Fix — Discoverable CLI Subcommands

## Target

Fix review findings about CLI discoverability and fragile top-level command
routing.

## Problem

The CLI previously intercepted `raw_args[0] == "library"` and
`raw_args[0] == "creator"` before building the main parser. As a result:

- `clipvault --help` only showed the legacy single-video command.
- `library` and `creator` commands were not discoverable.
- `clipvault --library <path> library rebuild-index` was parsed as a video
  command and produced confusing errors.

## Changes

- Added a top-level argparse command tree with:
  - `clipvault video`
  - `clipvault library`
  - `clipvault creator`
- Preserved legacy `clipvault <url>` behavior by mapping it to
  `clipvault video <url>`.
- Preserved `process_library_command()` and `process_creator_command()` as
  testable wrappers over the shared parser.
- Added tests for top-level help and legacy argument normalization.

## Program Logs

No runtime pipeline logs changed in this step. The fix is CLI parser
discoverability and routing.

## Verification

```powershell
.\clipvault.ps1 --help
.\clipvault.ps1 --library E:\VideoSubs library rebuild-index --dry-run
.\.venv\Scripts\python.exe -m pytest tests\test_cli.py -q
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q clipvault tests
git diff --check
```

Result:

```text
top-level help shows video/library/creator
library rebuild-index accepts top-level --library
18 passed
186 passed
No broken requirements found.
compileall clean
git diff --check clean
```
