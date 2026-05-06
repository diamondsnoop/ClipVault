# ClipVault 路线图

## 产品方向

ClipVault 是一个本地优先的视频字幕库。它的核心价值是可靠获取、保存和长期维护原始视频内容的字幕。

近期不应把项目做成通用 AI 笔记生成器。AI 摘要、问答和笔记生成可以在后续阶段加入，但前提是字幕获取和本地仓库管理已经足够稳定。

## 当前基线

当前已实现：

- CLI 命令：`clipvault`。
- Windows 启动脚本：`clipvault.ps1`。
- 本地 Web UI：`clipvault ui`。
- 通过 `yt-dlp` 处理 Bilibili URL。
- 通过通用 `yt-dlp` 路径验证 YouTube 字幕流程。
- 有平台字幕或自动字幕时优先使用。
- 无字幕时下载音频并回退本地 ASR。
- 使用 `faster-whisper` 本地 ASR。
- CUDA 自动选择，失败时回退 CPU。
- 字幕解析、导出、仓库、创作者、队列、认证和 UI server 的测试覆盖。
- 用户可见 stderr/stdout 程序日志。
- 输出文件：
  - `manifest.json`
  - `transcript.srt`
  - `transcript.txt`
  - `transcript.md`
- 当前仓库布局：
  - `library/<platform>/<creator>/<video title - id>/`
- 系列仓库布局：
  - `library/<platform>/<creator>/<series>/<video title - id>/`
- 完整旧缓存兼容：
  - `library/<creator>/<video title - id>/`
- 依赖拆分：
  - `requirements.lock`：基础依赖。
  - `requirements-gpu-win.lock`：可选 Windows NVIDIA GPU 运行时。
- 核心模块拆分：
  - `cli.py`
  - `adapters.py`
  - `platforms.py`
  - `subtitles.py`
  - `asr.py`
  - `library.py`
  - `series_rules.py`
  - `creators.py`
  - `auth.py`
  - `exporters.py`
  - `models.py`
  - `text.py`
  - `ui/server.py`

## 开发原则

- 从字幕获取向外构建。
- 把原始字幕视为主要资产。
- 在字幕库稳定前，生成笔记和 AI 摘要保持出 scope。
- 优先本地优先存储和开放文件格式。
- GPU 依赖保持可选。
- 通过程序日志让运行行为可观察。
- 在 `logs/development/` 记录有意义的开发步骤。
- 让项目对未来开源贡献者友好。
- 只有 manifest 状态和实际输出文件一致时，才把缓存视为完整。
- ASR 模型行为必须明确：当前只使用本地模型，除非有意实现自动下载。

## 手动验证样本

这些样本用于平台行为的手动或集成式检查。它们不进入默认单元测试，因为外部平台内容、字幕和访问规则会变化。

- Bilibili 主样本：闲木鱼《大明王朝》系列。
- Bilibili 次样本：马督公《睡前消息》系列，用作后续回归检查。
- YouTube：Jabzy，`History of the Middle East` 系列。
- Douyin：曾章见真章《曾章见真章创建的合集》系列。

每次手动验证都要记录准确 URL、日期、字幕来源、输出路径和失败模式。

## Phase 1：稳定字幕核心

目标：让现有字幕流程可靠、可测试、可维护。

状态：已完成，主线完成于 commit `e2e571c`，Phase 2 后继续补过 review 修复。

已完成工作：

- 增加字幕解析单元测试：
  - Bilibili JSON 字幕。
  - YouTube JSON3 字幕。
  - VTT。
  - SRT。
- 增加导出器测试：
  - `to_srt`。
  - `to_plain_text`。
  - `to_markdown`。
- 增加程序日志：
  - 元数据提取开始/成功/失败。
  - 字幕发现结果。
  - 音频下载开始/成功/失败。
  - ASR 开始/成功/失败。
  - CUDA fallback。
  - 导出路径。
- 改善错误信息：
  - 缺少 `ffmpeg`。
  - URL 不支持或提取失败。
  - 无字幕且音频下载失败。
  - ASR 模型缺失。
- 增加稳定 `manifest.json` schema version。

成功标准：

- 既有 Bilibili 流程继续可用。
- 测试覆盖字幕解析和导出格式。
- 用户能理解正在运行哪个阶段，以及失败原因。

## Phase 2：仓库结构和元数据

目标：让 ClipVault 成为可维护的字幕库，而不是一次性输出脚本。

状态：已完成，主线完成于 commit `650235b`，之后补过缓存和文档修复。

已完成工作：

- 引入更面向未来的仓库布局：
  - `library/<platform>/<creator>/<video title - id>/`
- 保留旧布局兼容：
  - `library/<creator>/<video title - id>/`
- 扩展 `manifest.json`：
  - `schema_version`
  - `platform`
  - `source_url`
  - `webpage_url`
  - `video_id`
  - `title`
  - `creator_name`
  - `creator_id`
  - `duration`
  - `upload_date`
  - `processed_at`
  - `subtitle_source`
  - `asr_model`
  - `asr_device`
  - `output_files`
- 基于 manifest 状态复用缓存，而不是只检查 `transcript.md`。
- 复用缓存前验证 manifest 中列出的输出文件实际存在。

成功标准：

- 新输出使用平台感知路径。
- Manifest 包含未来系列和创作者管理所需元数据。
- 现有完整缓存仍可使用。

## Phase 3：多平台字幕支持

目标：用同一套字幕流程支持主流视频平台。

优先级：

1. Bilibili 打磨。
2. YouTube 验证。
3. Douyin 研究和原型。

已完成和当前状态：

- 增加围绕 `yt-dlp` 元数据的平台识别。
- 验证 YouTube：
  - 人工字幕。
  - 自动字幕。
  - 音频 fallback。
- 平台特定 URL 补全和语言偏好隔离在适配器模块。
- 不对 Douyin 稳定性过度承诺。

近期验证：

- 2026-05-05：Bilibili 闲木鱼《大明王朝》单视频验证完成，`BV16G411973A`，ASR fallback，1290 segments，`small` 模型，CUDA。无登录验证中平台字幕需要登录，因此正确回退到 ASR。

成功标准：

- Bilibili 和 YouTube 都能通过同一 CLI 产生字幕输出。
- Manifest 和仓库路径记录平台名。
- Douyin 在被称为稳定支持前，必须有明确可行性结论。

## Phase 4：系列和创作者组织

目标：支持围绕创作者和 recurring series 的长期维护。

### Phase 4 Step 1：手动系列分组（已完成）

增加 `--series "Series Name"` CLI 参数。带系列的仓库路径：

```text
library/<platform>/<creator>/<series>/<video title - id>/
```

Manifest 包含 `"series": "Series Name"`。缓存边界严格：带 `--series` 的运行不会命中非系列缓存。

### Phase 4 Step 2：创作者和系列索引（已完成）

自动维护 JSON 索引，供仓库浏览使用：

- 创作者索引：`library/<platform>/<creator>/_index.json`，列出全部视频并聚合已知系列。
- 系列索引：`library/<platform>/<creator>/<series>/_index.json`，仅在使用系列时创建。
- 索引是普通 JSON，新处理和缓存命中都会更新。
- 视频按 `video_id` 去重，并按 `processed_at` 降序、标题升序排序。
- 索引中只保存相对路径，便于仓库迁移。

### Phase 4 Step 3：基于标题的自动系列规则（已完成）

当未传入 `--series` 时，可以用本地标题匹配规则自动归入系列：

- 规则文件：`library/<platform>/<creator>/_series_rules.json`。
- 支持 `title_contains` 关键词列表和可选 `title_regex` 正则。
- 第一条匹配规则生效，按文件顺序执行。
- 显式 `--series` 永远优先于自动规则。
- 缺失或无效规则文件不会阻断处理，只记录日志。
- 实现在 `clipvault/series_rules.py`。

### Phase 4 Step 4：仓库索引重建（已完成）

维护命令：

```powershell
clipvault library rebuild-index
clipvault library rebuild-index --library "E:\VideoSubs"
clipvault library rebuild-index --library "E:\VideoSubs" --dry-run
```

- 扫描仓库中的完整 `manifest.json`。
- 从零重建创作者和系列 `_index.json`。
- manifest 消失时移除 stale index 或 stale video entry。
- 无效或不完整 manifest 会通过 `[index] skipped manifest (...)` 日志跳过。
- 不下载视频、不抓字幕、不运行 ASR。

成功标准：

- 用户可以把同一创作者的视频归入命名系列。已完成。
- 未来创作者订阅可以复用相同元数据。已完成索引基础。
- 标题规则可在没有 `--series` 时自动归类。已完成。
- 索引过期时可以从磁盘恢复。已完成。

## Phase 5：创作者追踪和批量摄取

目标：支持关注创作者并收集新视频。

### Phase 5 Step 1：创作者来源注册（已完成）

本地注册创作者或频道来源：

```powershell
clipvault creator add <url> --name "Display Name"
clipvault creator list
```

- 保存到 `library/_creators.json`。
- 记录平台、显示名、来源 URL、添加时间和检查状态。
- 添加相同 source URL 是幂等操作，会更新显示名。
- 此步骤不抓取最近视频。

### Phase 5 Step 2：创作者抓取预览（已完成）

只读的最近条目发现：

```powershell
clipvault creator fetch <creator-id-or-name> --limit 20
```

- 使用 `library/_creators.json` 中记录的 `source_url`。
- 通过 `yt-dlp` 获取最近的 flat playlist/channel entries。
- 返回发现的视频标题和 URL JSON。
- 根据本地完整 manifest 标记每条为 `new` 或 `processed`。
- 更新 `last_checked_at`。
- 不处理字幕，不入队 ASR 任务。

### Phase 5 Step 3：抓取状态标记（已完成）

抓取预览会和本地完整 manifest 对比：

- `library_status: "processed"` 表示本地字幕库已经存在。
- `library_status: "new"` 表示可作为待摄取候选。
- 结果包含 `new_count` 和 `processed_count`。

### Phase 5 Step 4：字幕任务队列（已完成）

把新的创作者条目加入队列，但不立即处理：

```powershell
clipvault creator enqueue <creator-id-or-name> --limit 20
```

- 写入 pending jobs 到 `library/_queue.json`。
- 跳过本地已处理条目。
- 跳过已经在队列中的条目。
- 队列执行由 Step 5 处理。

### Phase 5 Step 5：队列执行（已完成）

通过现有单视频流程执行 pending 任务：

```powershell
clipvault queue status
clipvault queue list --status pending
clipvault queue run --limit 1
```

- `queue run` 默认只执行一个 pending job，避免意外批量 ASR。
- 成功任务标记为 `done` 并保存输出元数据。
- 失败任务标记为 `failed` 并保留 `last_error`。
- `--retry-failed` 允许显式重试。

成功标准：

- 可以检查已记录创作者的新视频。
- 不必手动粘贴每个视频 URL，也能把新视频加入摄取队列。

## Phase 6：桌面 Web UI

目标：让 ClipVault 不依赖命令行也能使用。

状态：MVP 已完成。

已实现：

- `clipvault ui` 子命令。
- 本地 HTTP server，只绑定 `127.0.0.1`。
- 启动时生成随机 token，API 请求通过 token 校验。
- 通过后台 job manager 运行长任务，并用 SSE 推送日志。
- 视频页：输入 URL、选择模型和设备、可选系列、force、keep audio。
- 仓库页：按平台、创作者、系列、视频浏览，并预览 transcript。
- 创作者页：添加来源、抓取预览、入队。
- 队列页：查看任务、移除任务、运行队列。
- 设置页：保存仓库路径、模型、设备和 cookies 路径。

成功标准：

- GUI 是稳定核心流程的薄外壳。已完成。
- CLI 继续完整支持。已完成。

## Phase 7：产品体验优化和文档建设

目标：在真实使用后修问题、优体验、补文档，不扩张新功能。

当前计划：

1. 改善 ASR 输出质量：
   - 处理中文 ASR 可能输出繁体的问题。
   - 改善 `transcript.md` 的可读性，避免长视频变成数千行时间戳列表。
2. 修复偶发 `JSONDecodeError`：
   - 增强 `update_manifest()` 调用边界和 JSON 读取防御。
3. 优化 Web UI 日志显示：
   - 日志分级着色。
   - 状态摘要。
   - 结果卡片增强。
4. 编写用户手册：
   - 新增 `docs/user-guide.md`。
5. 文档中文化：
   - 第一批：`README.md`、`AGENTS.md`。
   - 第二批：`docs/plan/roadmap.md`、`docs/mvp-development-summary.md`。
   - 第三批：`docs/plan/phase6-ui-spec.md`、`DESIGN.md`。

## 后续暂不做

- AI 笔记生成。
- 针对字幕的聊天和问答。
- 云同步。
- 移动端 App。
- Douyin 稳定支持声明。
- 自动事实核查。

这些能力只能在字幕库本身足够稳定后再重新评估。

## 近期任务

1. 先完成 Phase 7 文档中文化和用户手册。
2. 修复 Phase 7 中的 JSONDecodeError。
3. 改善 Markdown 输出可读性和中文繁简问题。
4. 优化 Web UI 日志体验。
5. 用真实 Bilibili 样本补充回归记录。
6. 继续把 AI 笔记生成留在后续阶段。
