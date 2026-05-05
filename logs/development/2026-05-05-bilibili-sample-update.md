# 2026-05-05: Bilibili Sample Update and Hardening

## Target

Update the manual validation samples before the next real-link regression pass.

## Changes

- Bilibili primary sample changed to 闲木鱼《大明王朝》系列.
- Bilibili secondary sample keeps 马督公《睡前消息》系列 for later regression checks.
- Douyin sample changed to 曾章见真章《曾章见真章创建的合集》系列.
- 王朝董事会《大明王朝》 was removed from the planned validation samples.
- Added Bilibili-focused URL identification tests for `space.bilibili.com` and
  `bilibili.com/list`.
- Added Bilibili `av...` flat-entry URL completion coverage.

## Program Logs

No runtime logging changed in this step.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_platforms.py -q
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Result:

```text
19 passed
195 passed
No broken requirements found.
git diff --check clean
```
