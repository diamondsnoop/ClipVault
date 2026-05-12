# Phase 7：产品体验优化与文档建设

> Status: completed
> Last updated: 2026-05-12
> Source of truth: Phase 7 质量修复、日志体验和文档建设的阶段计划。
> Superseded by: `docs/plan/phase8-source-collection-workflow.md` for 合集/来源后续开发。

## 背景

Phase 6 完成了桌面 Web UI，用户开始实机使用。在真实 B 站视频（一条闲木鱼《大明王朝1566》系列）的处理过程中，发现了三类问题：

1. **输出质量**：ASR 结果繁简混杂、Markdown 不可读
2. **程序健壮性**：JSON 解析偶发崩溃
3. **UI 体验**：日志显示不舒适、缺少用户文档

本 Phase 聚焦于修问题、优体验、建文档，不扩张新功能。

---

## 问题清单

### Issue 1：ASR 输出繁体而非简体

- **严重程度**：中
- **现象**：faster-whisper 对《大明王朝》等历史剧内容输出繁体中文
- **根因**：`asr.py:90` 设置 `language="zh"`，但 Whisper 模型对于历史题材内容可能倾向繁体。当前管线无繁→简转换
- **方向**：对中文 ASR 结果增加繁→简转换环节（`opencc` 或 LLM 后处理）

### Issue 2：Markdown 输出为时间戳列表，不可读

- **严重程度**：中
- **现象**：`transcript.md` 格式为 `- \`MM:SS\` segment text`，每句一行，视频长则数千行
- **根因**：`exporters.py:to_markdown()` 直接将分句映射为带时间戳的列表项
- **方向**：重写 `to_markdown()` 为段落合并逻辑（按时间间隙 + 标点智能分段，去时间戳）

### Issue 3：JSONDecodeError 偶发崩溃

- **严重程度**：低（偶发但影响体验）
- **现象**：`[error] Expecting value: line 2 column 2 (char 2)` 出现在 `[index] creator:` 之后
- **根因**：`cli.py:623` 的 `update_manifest()` 调用在 try/except 保护之外。`update_manifest` 内部 `json.loads` 读取 `manifest.json`，若文件瞬时不可读则抛异常直达 `main()`
- **修复**：将 `update_manifest` 移入 try/except 块（cli.py:626），同时给 `update_manifest` 增加防御

### Issue 4：Web 前端日志黑框体验差

- **严重程度**：低（UX 优化）
- **现象**：日志区域是深色背景 + 等宽字体，能工作但不舒适
- **方向**：
  - 日志行增加类型标记（info / warn / error / success），前端按类型着色
  - 增加状态摘要条（如「正在转写…」、「处理完成 ✓」）
  - 结果展示卡片增加亮点（片段数、字幕源、耗时等）
  - 可选：日志自动滚动到底部、支持折叠/展开

### Issue 5：缺少用户手册

- **严重程度**：中
- **现象**：现有文档（README、AGENTS、roadmap）面向开发者和 AI Agent，普通用户无入门路径
- **方向**：新写一份 `docs/user-guide.md`，从用户视角介绍产品用法、常见工作流、典型场景

### Issue 6：现有英文文档需要中文化

- **严重程度**：低（但对中文用户重要）
- **现象**：项目面向中文用户（B 站为主平台），但文档全是英文
- **待重写文档列表**：

| 文件 | 类型 | 内容 | 优先级 |
|------|------|------|--------|
| `README.md` | 用户/开发者 | 安装、命令、布局、cookie 登录 | 高 |
| `AGENTS.md` | AI Agent | 项目目标、开发规则、日志规范 | 高 |
| `docs/plan/roadmap.md` | 规划 | Phase 1-6 完整路线图 | 中 |
| `docs/mvp-development-summary.md` | 总结 | MVP 完成总结 | 中 |
| `docs/plan/phase6-ui-spec.md` | 规格 | Phase 6 UI 实现规格 | 低（已实现） |
| `DESIGN.md` | 设计 | UI 设计 Token 参考 | 低 |

---

## Phase 7 任务规划

### Step 1：Markdown 段落化 + 繁简转换

**目标**：让 LLM 一次处理后处理解决 Issue 1 + Issue 2

**方案**：
- 新增 `clipvault/llm.py` 模块
- CLI 增加 `--polish` 标志（可选，默认关闭）
- Web UI 视频标签页增加「LLM 润色」开关
- 支持 OpenAI 兼容 API（用户配置 base_url + api_key）
- Prompt 设计：传入原始字幕文本 → LLM 完成繁→简 + 错字修正 + 段落排版
- LLM 处理后的 Markdown 直接覆盖 `transcript.md`

**API Key 管理**：
- 环境变量 `CLIPVAULT_LLM_KEY`
- Web UI 设置页增加配置项

### Step 2：JSONDecodeError 修复

**目标**：消除偶发崩溃

**修改**：
- `cli.py`：将 `update_manifest` 调用移入 try/except 块
- `library.py`：`update_manifest` 内部增加 `json.JSONDecodeError` 捕获，给出带文件路径的错误信息

### Step 3：日志显示优化

**目标**：提升 Web UI 日志区域的可读性

**方案**：
- CSS 重新设计日志面板（保持整体风格与 DESIGN.md 一致）
- 日志行按 `[xxx]` 前缀自动分类着色
- 增加状态摘要组件
- 结果卡片视觉升级

### Step 4：用户手册编写

**目标**：写一份面向普通用户的使用指南

**内容大纲**：
1. ClipVault 是什么
2. 安装（Windows）
3. 快速开始：处理第一个视频
4. 仓库管理：浏览、搜索、打开文稿
5. 创作者追踪：订阅、拉取、队列
6. 设置说明：模型选择、设备、Cookie
7. 常见问题

### Step 5：文档中文化

**目标**：将英文文档重写为中文

**第一批（高优先级）**：
- `README.md` → 重写为中文
- `AGENTS.md` → 重写为中文

**第二批（中优先级）**：
- `docs/plan/roadmap.md`
- `docs/mvp-development-summary.md`

**第三批（低优先级，可选）**：
- `docs/plan/phase6-ui-spec.md`
- `DESIGN.md`

---

## 里程碑

| Step | 内容 | 预计工作量 |
|------|------|-----------|
| Step 1 | LLM 后处理 | 主要 |
| Step 2 | JSONDecodeError 修复 | 微小 |
| Step 3 | 日志显示优化 | 中等 |
| Step 4 | 用户手册 | 中等 |
| Step 5 | 文档中文化 | 中等 |

---

## 不在本 Phase 范围内

- AI 笔记生成（仍属于 Phase 8+）
- 新平台支持
- 搜索/全文检索
- 云端同步

这些保持 roadmap 中「Out of Scope Until Later」的定位不变。
