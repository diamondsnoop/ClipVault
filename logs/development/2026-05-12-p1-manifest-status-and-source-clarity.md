## Target

完成 Phase 7 的 P1 收尾，让失败任务在仓库内可追踪、让字幕来源解释更清楚，并让 Web 用户能直接找到任务日志目录。

## Steps

1. 给 `manifest.json` 增加显式处理状态字段，并让失败路径写回失败原因。
2. 给平台字幕 / 自动字幕 / 本地 ASR 增加可读来源说明。
3. 让 Web UI 在视频结果、仓库详情和任务日志区域暴露更多状态信息。
4. 补最小回归测试和用户手册说明。

## Changes

- `clipvault/library.py`
  - `build_manifest()` 默认写入 `processing_state`、`failed_at`、`last_error`。
  - `is_completed()` 现在会拒绝 `started` / `failed` 状态的半成品目录。
  - 新增 `describe_subtitle_source()`，统一生成字幕来源标签和解释文案。
- `clipvault/cli.py`
  - 缓存命中返回 `source_label` / `source_detail`。
  - 成功路径会把 `processing_state=completed`、字幕来源标签和说明写回 manifest。
  - 失败路径会把 `processing_state=failed`、`failed_at`、`last_error` 写回 manifest。
- `clipvault/ui/server.py`
  - 仓库树视频节点返回 `processing_state`、`last_error`、来源标签和说明。
  - `/api/open-path` 允许打开任务日志根目录下的路径。
- `clipvault/ui/static/index.html`
  - 视频页和队列页增加“日志动作”区域。
- `clipvault/ui/static/style.css`
  - 增加任务说明和错误说明样式。
- `clipvault/ui/static/app.js`
  - 视频结果卡片、仓库详情、日志动作区支持显示字幕来源说明、失败说明和“打开任务日志”按钮。
- `docs/user-guide.md`
  - 增加任务状态、字幕来源和任务日志目录说明。
- `tests/test_library.py`
  - 覆盖字幕来源说明和失败/处理中 manifest 不算完成。
- `tests/test_cli.py`
  - 覆盖失败任务会把状态与错误原因写回 manifest。

## Verification

- `node --check clipvault\ui\static\app.js`
  - 通过，约 0.226s。
- `python -m compileall clipvault`
  - 通过，约 0.170s。
- 待执行：
  - `pytest tests/test_library.py tests/test_cli.py -q`
  - Web UI 手工回归：查看结果卡片、仓库详情、“打开任务日志”按钮。

## Follow-ups

- 下一步继续做 P2：视频页输入区和日志区重排。
- 如果后续确认日志打开入口足够稳定，可继续把仓库 / 创作者 / 队列 / 设置页统一成同一信息层级结构。
