# ClipVault 文档入口

## 目的

这个目录用于区分“当前事实”“后续计划”“历史记录”和“用户说明”。后续维护时，先看本文件，再进入具体文档。

## 文档权威顺序

1. `AGENTS.md`
   - 面向 AI agent 和开发者的硬规则。
   - 约束项目目标、开发边界、日志要求、Git 卫生和安全注意事项。
   - 遵循优先级最高，但不承载详细产品路线。

2. `DESIGN.md`
   - Web UI 的视觉设计规范。
   - 前端/UI 任务必须遵循。
   - 如果效果图和 `DESIGN.md` 冲突，以 `DESIGN.md` 为准。

3. `docs/README.md`
   - 文档导航和治理规则。
   - 用来判断应该读哪份文档。

4. `docs/plan/roadmap.md`
   - 当前产品路线图和阶段状态。
   - 适合判断“项目整体走到哪里”。

5. `docs/plan/phase*.md`
   - 阶段设计、实现说明或交接文档。
   - 可能是已完成阶段的历史文档，必须先看文档头部的 `Status`。

6. `docs/user-guide.md`
   - 面向普通用户的使用手册。
   - 不应塞入开发路线、内部实现细节或 agent 规则。

7. `logs/development/`
   - 开发过程记录。
   - 只用于追溯“为什么这么改”和“当时验证了什么”。
   - 不应作为当前产品规范或实现计划的唯一依据。

8. `logs/program/`
   - 程序日志规范和运行时可观测性说明。
   - 修改日志输出、错误信息和任务状态时参考。

## 状态标记

规划和阶段文档应在标题下方保留状态块：

```text
> Status: active / planned / completed / historical
> Last updated: YYYY-MM-DD
> Source of truth: ...
> Supersedes: ...
> Superseded by: ...
```

字段说明：

- `active`：当前仍在指导开发。
- `planned`：已确认方向，但尚未开始或尚未完成。
- `completed`：阶段已完成，作为实现记录保留。
- `historical`：历史总结或旧设计，只能作为背景参考。
- `Source of truth`：说明这份文档对哪个范围负责。
- `Supersedes`：说明它替代了哪份旧文档或旧做法。
- `Superseded by`：说明它已被哪份新文档或实际实现取代。

## 当前阅读路径

### 了解项目当前状态

1. `AGENTS.md`
2. `docs/README.md`
3. `docs/plan/roadmap.md`
4. 最新的 `docs/plan/phase*.md`

### 做 Web UI

1. `AGENTS.md`
2. `DESIGN.md`
3. `docs/plan/phase8-source-collection-workflow.md`，如果任务涉及合集或来源链路。
4. `logs/development/` 中对应日期的开发记录，仅作为补充。

### 修改用户使用方式

1. `docs/user-guide.md`
2. `README.md`
3. 对应功能的 `docs/plan/phase*.md`

### 排查历史决策

1. `docs/plan/roadmap.md`
2. 对应 phase 文档
3. `logs/development/`

## 维护规则

- 不要把开发流水账写进 `AGENTS.md`。
- 不要把未实现功能写进用户手册，除非明确标注“暂未实现”。
- 新增阶段计划时放在 `docs/plan/`。
- 完成一次有意义开发后，在 `logs/development/` 写开发日志。
- 修改 Web UI 风格时，不要新增独立风格说明，优先更新或遵循 `DESIGN.md`。
- 如果文档和实际代码冲突，先以代码为准，并更新文档。

