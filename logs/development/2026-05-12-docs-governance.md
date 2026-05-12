## Target

整理 ClipVault 文档结构，让后续接手者能区分当前规范、阶段计划、用户说明和开发流水账。

## Steps

1. 检查现有 `docs/`、`logs/`、`AGENTS.md` 和 `DESIGN.md` 的职责。
2. 新增 `docs/README.md` 作为文档入口，说明文档权威顺序、状态标记和阅读路径。
3. 给现有路线图、阶段文档、MVP 总结和用户手册增加状态头。
4. 在 `AGENTS.md` 增加简短文档使用规则，要求后续 agent 先阅读 `docs/README.md`。

## Changes

- `docs/README.md`
  - 新增文档导航、权威顺序、状态标记和维护规则。
- `docs/plan/roadmap.md`
  - 标记为 active。
- `docs/plan/phase6-ui-spec.md`
  - 标记为 completed，并说明已被后续 UI 实现取代。
- `docs/plan/phase7-quality-and-docs.md`
  - 标记为 completed，并指向 Phase 8 文档作为合集/来源后续开发依据。
- `docs/plan/phase8-source-collection-workflow.md`
  - 标记为 planned，作为 Phase 8 合集/来源资产化开发依据。
- `docs/mvp-development-summary.md`
  - 标记为 historical。
- `docs/user-guide.md`
  - 标记为 active。
- `AGENTS.md`
  - 增加文档使用规则，避免把阶段计划和开发日志继续塞进 agent 约束。

## Verification

- 待执行：Markdown 空白检查和 Git 状态确认。

## Follow-ups

- 后续如果文档继续增长，可以把旧 phase 文档归档到 `docs/archive/`，但当前先用状态头解决“误读旧文档”的问题。

