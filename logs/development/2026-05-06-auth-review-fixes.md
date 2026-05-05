# 2026-05-06: Auth Review Fixes

## Target

Fix review findings from the Bilibili login and cookie integration pass.

## Steps

1. Harden `--cookies` parsing.
   - Normalize optional `--cookies` values before argparse consumes
     subcommands or video URLs as cookie paths.
   - Keep global `--cookies` usable while letting command-local `--cookies`
     override it.

2. Keep CLI stdout machine-readable.
   - Render terminal QR codes to stderr so stdout can remain JSON.

3. Reduce generated cookie-file lifetime.
   - Register cookie cache cleanup at interpreter exit.
   - Clear generated cookie cache after CLI command execution.

## Program Logs

- Stored credentials still log only file paths, never cookie values.
- Generated cookie cache files are deleted after CLI execution or process exit.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_auth.py tests\test_cli.py tests\test_login.py tests\test_credentials.py -q
.\.venv\Scripts\python.exe -m compileall -q clipvault tests
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Results:

- Targeted auth/CLI/login/credentials tests: 82 passed.
- Full test suite: 265 passed.
- `compileall`: clean.
- `pip check`: no broken requirements.
- `git diff --check`: clean.

Note: Windows ACLs on local pytest/pycache directories required running the
verification commands outside the filesystem sandbox.
