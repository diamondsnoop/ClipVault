# 2026-05-04: Phase 5 Step 4 — Transcript Job Queue

## Target

Add a local pending-job queue for new creator entries discovered by
`clipvault creator fetch`.

This step still does not run transcript jobs. It only records pending work.

## Steps

1. Added `library/_queue.json` queue helpers.
2. Added `clipvault creator enqueue <selector> --limit N`.
3. Reused creator fetch preview and local processed/new marking.
4. Skipped entries already processed in the library.
5. Skipped entries already present in the queue.
6. Added tests for enqueue, dedupe, processed skipping, and invalid queue
   recovery.
7. Updated README, roadmap, and agent guidance.

## Program Logs

Queue commands report:

```text
[queue] added: <n>, skipped processed: <n>, skipped existing: <n>
[queue] path: <library/_queue.json>
```

## Verification

```powershell
.\clipvault.ps1 creator enqueue --help
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q clipvault tests
git diff --check
```

Result:

```text
183 passed
No broken requirements found.
compileall clean
git diff --check clean
```

## Follow-ups

Next Phase 5 step should add queue execution, probably as a separate command
that processes pending jobs one by one through the existing `process_video()`
pipeline and records per-job success or failure.
