# 2026-05-11 Phase 7 Quality And Docs

## Target

完成 Phase 7 的代码与文档收尾，重点解决：

- `manifest.json` 偶发解析崩溃
- `transcript.md` 可读性差
- 中文 ASR 繁简混杂
- Web UI 日志体验不足
- 程序日志和 CLI 帮助仍以英文为主
- 普通用户缺少可直接上手的中文文档

## Steps

1. 加固 `update_manifest()`，让坏 JSON、缺失文件和写入失败都能给出带路径的中文错误，并让主流程在 manifest 更新失败时不直接崩溃。
2. 重写 Markdown 导出逻辑，把逐句列表改成段落化正文；按时间间隔、句末标点和段落长度切分。
3. 增加可配置的中文转简后处理，默认只对 ASR 结果启用，并在依赖缺失时降级为警告而不是中断主流程。
4. 把 CLI、认证、平台抓取、索引维护和 UI SSE 日志统一为中文阶段日志。
5. 升级 Web UI：增加日志级别样式、状态摘要、结果卡片补充 ASR 信息，并把 `compute_type`、中文转简开关补到视频页、队列页、设置页。
6. 补齐 README、用户手册、认证日志规范，并更新依赖锁文件。

## Changes

- 新增 [clipvault/runtime_logs.py](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/clipvault/runtime_logs.py)
  - 提供统一的中文阶段日志格式。
- 新增 [clipvault/postprocess.py](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/clipvault/postprocess.py)
  - 提供基于 OpenCC 的中文转简后处理。
- 修改 [clipvault/cli.py](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/clipvault/cli.py)
  - 增加 `--simplify-chinese/--no-simplify-chinese`
  - 加固 manifest 更新边界
  - 汉化 CLI 帮助和运行日志
  - 补上 `sys` 导入，修复 `main()` 入口隐患
- 修改 [clipvault/exporters.py](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/clipvault/exporters.py)
  - 段落化输出 `transcript.md`
- 修改 [clipvault/library.py](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/clipvault/library.py)
  - `update_manifest()` 增加坏 JSON 恢复和中文异常信息
- 修改 [clipvault/auth.py](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/clipvault/auth.py)、[clipvault/login.py](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/clipvault/login.py)、[clipvault/platforms.py](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/clipvault/platforms.py)、[clipvault/creators.py](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/clipvault/creators.py)、[clipvault/series_rules.py](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/clipvault/series_rules.py)、[clipvault/subtitles.py](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/clipvault/subtitles.py)、[clipvault/asr.py](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/clipvault/asr.py)
  - 汉化运行日志和关键错误信息
- 修改 [clipvault/ui/server.py](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/clipvault/ui/server.py)、[clipvault/ui/static/index.html](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/clipvault/ui/static/index.html)、[clipvault/ui/static/app.js](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/clipvault/ui/static/app.js)、[clipvault/ui/static/style.css](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/clipvault/ui/static/style.css)
  - 增加状态摘要
  - 增加日志级别着色
  - 展示 ASR 模型/设备
  - 补齐 `compute_type` 和中文转简设置
  - 统一前端回退文案为中文
- 修改 [pyproject.toml](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/pyproject.toml)、[requirements.lock](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/requirements.lock)、[uv.lock](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/uv.lock)
  - 增加 `opencc-python-reimplemented`
- 修改 [README.md](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/README.md)
  - 补充中文转简能力说明和命令示例
- 新增 [docs/user-guide.md](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/docs/user-guide.md)
  - 提供面向普通用户的中文上手文档
- 修改 [logs/program/auth-cookies.md](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/logs/program/auth-cookies.md)
  - 汉化认证访问日志规范
- 更新测试：
  - [tests/test_cli.py](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/tests/test_cli.py)
  - [tests/test_exporters.py](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/tests/test_exporters.py)
  - [tests/test_library.py](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/tests/test_library.py)
  - [tests/test_ui_server.py](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/tests/test_ui_server.py)
  - [tests/test_credentials.py](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/tests/test_credentials.py)
  - 以及认证、登录、创作者、系列规则相关测试

## Verification

- `E:\myproject\ClipVault\.venv\Scripts\python.exe -m pytest -q`
  - 结果：`278 passed`
- `E:\myproject\ClipVault\.venv\Scripts\python.exe -m clipvault --help`
  - 结果：CLI 帮助可正常输出，主帮助已中文化
- `node --check clipvault\ui\static\app.js`
  - 结果：通过
- `E:\myproject\ClipVault\.venv\Scripts\python.exe -m pip check`
  - 结果：`No broken requirements found.`
- `uv lock`
  - 结果：已更新 `uv.lock`，新增 `opencc-python-reimplemented`

## Follow-ups

- 当前没有补做浏览器里的人工视觉回归；后续若继续迭代 UI，可再做一次本地实际操作检查。
- `docs/plan/phase6-ui-spec.md` 和 `DESIGN.md` 仍保留原有低优先级内容，可在后续文档整理时继续中文化。

## 2026-05-12 P0 Update

### Target

补齐 Web 任务可观测性的 `P0` 问题，确保：

- 任务日志会落盘保存，不再只存在内存里
- 前端不会把失败任务误显示为成功
- 失败时能返回可直接排查的摘要和日志目录

### Steps

1. 在 [clipvault/ui/server.py](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/clipvault/ui/server.py) 为任务增加日志目录、日志文件和错误上下文。
2. 让任务日志优先写入 `%APPDATA%\\ClipVault\\jobs`，不可写时自动回退到库目录 `_job_logs`，再回退到工作树 `.tmp/jobs`。
3. 让前端在任务开始和任务结束时都展示日志目录，并且只在 `done.status == "succeeded"` 时显示成功。
4. 增加日志目录回退、失败摘要和任务快照相关测试。

### Verification

- 合成成功任务
  - 结果：成功写出 `job.json`、`stderr.log`、`stdout.txt`、`result.json`
  - 日志目录：`C:\Users\24967\.codex\worktrees\0f02\ClipVault\.tmp\jobs\20260512-102739-623-video-p0check02`
- 合成失败任务
  - 结果：任务状态为 `failed`，`error` 和 `error_context` 都包含中文排查信息
  - 日志目录：`C:\Users\24967\.codex\worktrees\0f02\ClipVault\.tmp\jobs\20260512-110041-796-video-p0fail02`
- `pytest tests/test_ui_server.py -q`
  - 当前环境失败，原因不是 `P0` 回归，而是 `pytest tmpdir` 在本机创建的 `pytest-of-24967` 目录出现 ACL 异常，连当前用户也无法重新枚举或删除。
  - 已记录该环境问题，当前阶段以合成任务验收 `P0` 行为。
