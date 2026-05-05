# Authenticated Access Program Logs

ClipVault may use a local cookies file when a platform needs logged-in access.
Logs must confirm whether authenticated access is enabled without exposing
credential contents.

Current runtime log messages:

- `[auth] using ClipVault credentials from <path>` — stored credentials were
  read from ClipVault's auth file and converted into a temporary Netscape
  cookie file for the current process.
- `[auth] cookies file: <path>` — a cookies file was accepted and passed to
  `yt-dlp`.
- `[auth] cookies loaded for HTTP requests: <path>` — a cookies file was loaded
  for direct subtitle URL downloads.
- `[error] cookies file not found: <path>` — the configured cookies path does
  not exist or is not a file.
- `[error] failed to load cookies file <path>: <reason>` — the file exists but
  cannot be parsed as a Netscape cookies file.

Logging rules:

- Never print cookie values.
- Never include cookies file contents in bug reports.
- Printing the local path is acceptable because it helps users find stale or
  misplaced credential files.
- ClipVault-generated cookie cache files must be cleared when CLI execution or
  the Python process exits.
- If a platform still denies access while cookies are enabled, the next checks
  are: confirm the file is Netscape format, export fresh cookies, verify the
  account can open the video in a browser, and update `yt-dlp`.
