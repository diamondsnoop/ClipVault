# 2026-05-07 文档中文化

## Target

根据 Phase 7 文档建设计划，优先将高优先级和中优先级英文文档中文化，并同步修正 MVP/UI 状态描述。

## Steps

- 已检查 `docs/` 目录和当前 git 状态，确认 `docs/plan/phase7-quality-and-docs.md` 为既有未跟踪文件，本轮不修改。
- 已中文化高优先级文档：
  - `README.md`
  - `AGENTS.md`
- 已中文化中优先级文档：
  - `docs/plan/roadmap.md`
  - `docs/mvp-development-summary.md`
- 已把过期的 GUI 未实现描述更新为本地 Web UI MVP 已完成状态。

## Changes

- `README.md`：改为中文用户入口，补充本地 Web UI、cookies、GPU、仓库布局、自动系列规则、创作者队列和验证命令。
- `AGENTS.md`：改为中文 Agent/贡献者指南，更新当前范围、仓库结构、开发规则和近期路线。
- `docs/plan/roadmap.md`：改为中文路线图，补充 Phase 6 已完成和 Phase 7 目标。
- `docs/mvp-development-summary.md`：改为中文 MVP 总结，保留验证样本、模块说明、CLI/API/data files 和已知限制。

## Verification

- 已用 `rg` 检查 `README.md`、`AGENTS.md`、`docs/plan/roadmap.md`、`docs/mvp-development-summary.md` 中是否仍有 `Not yet implemented` 等过期描述。
- 未运行代码测试；本轮只修改 Markdown 文档。

## Follow-ups

- Phase 7 第三批低优先级文档仍可继续中文化：
  - `docs/plan/phase6-ui-spec.md`
  - `DESIGN.md`
- 仍需新增普通用户手册 `docs/user-guide.md`。
