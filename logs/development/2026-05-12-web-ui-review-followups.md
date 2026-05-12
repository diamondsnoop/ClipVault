## Target

处理 `3d99a92` Web UI review 中不应延后到 Phase 8 的体验和代码一致性问题。

## Steps

1. 补回应用内字幕阅读能力，不再只把用户带到资源管理器。
2. 收敛合集和来源入口的文案，避免按钮暗示未完成的批量链路。
3. 统一 `humanSteps` 更新方式，减少直接突变全局数组。
4. 持久化侧边栏折叠状态。

## Changes

- `clipvault/ui/static/index.html`
  - 新增字幕阅读器弹层结构。
- `clipvault/ui/static/app.js`
  - 新增应用内字幕阅读器，点击收藏夹字幕的“查看字幕”后读取 `/api/library/transcript`。
  - 阅读器提供“打开文件夹”作为次级操作。
  - 新增工作流步骤 helper，来源和合集不再直接突变 `humanSteps`。
  - 合集模式明确说明当前可用方式，来源模式明确说明批量勾选获取尚未接入。
  - 侧边栏折叠状态写入 `localStorage`。
- `clipvault/ui/static/style.css`
  - 新增阅读器弹层样式，保持 warm cream / coral / hairline 的现有设计语言。

## Verification

- `node --check clipvault\ui\static\app.js` 通过。
- `Invoke-WebRequest http://127.0.0.1:8080/` 返回 200，页面包含阅读器结构。
- `Invoke-WebRequest http://127.0.0.1:8080/app.js` 返回 200，包含 `查看字幕`、`openTranscriptReader`、`localStorage` 和 `setWorkflowSteps`。
- `git diff --check` 通过。

## Follow-ups

- 后续可以在阅读器中增加全文搜索、时间戳跳转和复制片段。
- 真正的合集/来源批量清单仍按 `docs/plan/phase8-source-collection-workflow.md` 实现。
