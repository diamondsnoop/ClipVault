# ClipVault MVP 开发总结

> Status: historical
> Last updated: 2026-05-12
> Source of truth: MVP 阶段完成情况的历史总结。
> Superseded by: `docs/plan/roadmap.md` for 当前路线判断。

## 结论

ClipVault MVP 已经达到当前计划中的功能完整状态。

MVP 的目标不是先做 AI 笔记产品，而是验证并稳定一个本地优先的字幕库：

1. 接收视频 URL。
2. 优先获取平台字幕或自动字幕。
3. 无字幕时回退到本地 ASR。
4. 导出 `srt`、`txt` 和 `md`。
5. 把输出保存在可维护的本地仓库结构中。
6. 支持创作者、系列组织和基础批量摄取。
7. 提供一个覆盖同一核心流程的简单桌面 Web UI。

已手动验证：

- YouTube：Jabzy `History of the Middle East`，自动字幕，983 segments。
- Bilibili：一条闲木鱼《大明王朝》，无平台字幕，CUDA ASR fallback，1290 segments。

Douyin 已能被识别并路由为平台，但真实链接验证尚不稳定，因为当前 `yt-dlp` 提取需要 fresh Douyin cookies。Douyin 应视为原型支持，不应宣传为稳定 MVP 路径。

## 已完成内容

### Phase 1：字幕核心

已完成。

实现了可靠的单视频字幕流程：

- 通过 `yt-dlp` 提取元数据。
- 发现平台字幕。
- 解析 Bilibili JSON、YouTube JSON3、VTT 和 SRT。
- 音频下载 fallback。
- 通过 `faster-whisper` 本地 ASR。
- CUDA 自动选择，失败时 CPU fallback。
- 导出 `transcript.srt`、`transcript.txt`、`transcript.md`。
- 元数据、字幕、音频下载、ASR、导出、缓存、索引阶段都有用户可见程序日志。

### Phase 2：仓库和元数据

已完成。

输出布局调整为：

```text
library/<platform>/<creator>/<video title - id>/
```

手动或自动分配系列后：

```text
library/<platform>/<creator>/<series>/<video title - id>/
```

每个视频目录包含：

```text
manifest.json
transcript.srt
transcript.txt
transcript.md
source_audio.m4a   # 仅 --keep-audio 时存在
```

`manifest.json` 是缓存、索引和 UI 浏览的稳定元数据记录。缓存完整性检查同时验证 manifest 状态和实际输出文件。

### Phase 3：平台路径

Bilibili 和 YouTube 已完成，Douyin 仍为原型。

- Bilibili 是主要验证路径。
- YouTube 字幕和自动字幕已验证。
- Douyin URL 识别和 adapter helper 已存在，但稳定字幕提取仍依赖平台访问和 cookies。

### Phase 4：系列和索引

已完成。

实现：

- 手动 `--series`。
- 创作者索引：`library/<platform>/<creator>/_index.json`。
- 系列索引：`library/<platform>/<creator>/<series>/_index.json`。
- `library rebuild-index`。
- 通过 `_series_rules.json` 做基于标题的自动系列规则。

系列规则是本地 JSON 文件：

```text
library/<platform>/<creator>/_series_rules.json
```

示例：

```json
{
  "schema_version": 1,
  "rules": [
    {
      "series": "History of the Middle East",
      "title_contains": ["History of the Middle East"],
      "title_regex": null
    }
  ]
}
```

### Phase 5：创作者追踪和队列

已完成。

实现：

- 创作者来源注册：`library/_creators.json`。
- `creator add`。
- `creator list`。
- `creator fetch`。
- `creator enqueue`。
- 队列文件：`library/_queue.json`。
- `queue status`。
- `queue list`。
- `queue run`。

队列任务通过和手动输入视频 URL 相同的 `process_video()` 流程执行。

### Phase 6：桌面 Web UI

MVP 已完成。

实现了由 ClipVault 自己提供服务的本地 Web UI：

- 视频页：粘贴 URL，选择模型/设备，可选系列、force、keep audio，查看日志和结果。
- 仓库页：浏览平台/创作者/系列/视频树，读取字幕，打开输出目录。
- 创作者页：添加创作者、抓取最近视频、入队新视频。
- 队列页：查看任务、移除任务、运行队列、流式日志。
- 设置页：保存仓库路径、ASR 模型/设备、cookies 路径。

UI 只在本地运行，使用随机 token。Server 绑定 `127.0.0.1`。

## 项目结构

### 根目录文件

```text
pyproject.toml
```

项目元数据、依赖、包发现和 CLI 入口：

```text
clipvault = "clipvault.cli:main"
```

```text
requirements.lock
requirements-gpu-win.lock
uv.lock
```

固定依赖文件。GPU 运行时单独拆分，因为 Windows NVIDIA wheel 体积较大。

```text
clipvault.ps1
```

Windows 本地开发启动脚本。

```text
README.md
```

用户快速开始、命令示例、登录说明、输出布局和常见工作流。

```text
AGENTS.md
```

未来 agent 和贡献者的开发规则：分步开发、开发日志、程序日志、验证样本和开源维护标准。

```text
DESIGN.md
```

桌面 Web UI 的设计参考。

```text
.gitignore
```

忽略 `.venv/`、`.tmp/`、`library/`、`.secrets/`、`.claude/`、缓存和 cookies 文件等本地运行状态。

### Python 包

```text
clipvault/cli.py
```

主 CLI 入口和流程编排。定义顶层命令：

- `video`
- `library`
- `creator`
- `queue`
- `auth`
- `ui`

也包含核心端到端视频流程 `process_video()`。

```text
clipvault/platforms.py
```

平台检测、语言偏好和通过 `yt-dlp` 的元数据提取。

```text
clipvault/adapters.py
```

平台适配边界，用于把扁平 playlist/channel 条目补全成可用视频 URL。覆盖 Bilibili、YouTube 和 Douyin URL 形态。

```text
clipvault/subtitles.py
```

字幕选择和解析：

- Bilibili JSON。
- YouTube JSON3。
- VTT。
- SRT。

`get_platform_subtitles()` 应用平台语言优先级，并返回 segments 和来源描述，例如 `subtitle:en:json3` 或 `automatic_caption:en-orig:json3`。

```text
clipvault/asr.py
```

通过 `faster-whisper` 做本地 ASR。解析设备和 compute type，使用本地缓存模型，返回字幕 segments。

```text
clipvault/exporters.py
```

把 transcript segments 转换为：

- SRT。
- 纯文本。
- Markdown。

```text
clipvault/library.py
```

仓库路径生成、manifest helper、缓存完整性检查、创作者/系列索引和索引重建逻辑。

```text
clipvault/series_rules.py
```

基于标题的系列分配规则。手动 `--series` 优先于规则。

```text
clipvault/creators.py
```

创作者注册、抓取预览、processed/new 状态检测、队列创建、队列列表和队列持久化。

```text
clipvault/auth.py
clipvault/login.py
clipvault/credentials.py
```

凭据处理：

- Bilibili 二维码登录。
- 凭据保存到 `%APPDATA%\clipvault\auth.toml`。
- 转换为临时 Netscape cookies 供 `yt-dlp` 使用。
- Auth 列表和登出。

```text
clipvault/models.py
clipvault/text.py
```

小型共享数据结构和文本 helper。

### UI 包

```text
clipvault/ui/server.py
```

桌面 UI 的本地 HTTP server。使用 `ThreadingHTTPServer`，绑定 `127.0.0.1`，并通过随机 token 保护读写 API。

重要 API：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/status` | 健康检查和版本信息 |
| GET | `/api/settings` | 读取 UI 设置 |
| POST | `/api/settings` | 保存 UI 设置 |
| POST | `/api/video` | 启动视频处理 job |
| GET | `/api/process/status` | 获取当前 job 状态 |
| GET | `/api/process/events` | 通过 SSE 流式获取 job 日志/结果 |
| POST | `/api/process/stop` | 停止当前 job |
| GET | `/api/library` | 读取仓库树 |
| GET | `/api/library/transcript` | 读取字幕内容 |
| GET | `/api/library/video` | 读取 manifest 和 transcript 详情 |
| POST | `/api/library/rebuild-index` | 重建索引 |
| POST | `/api/open-path` | 打开输出目录，限制在 library root 内 |
| GET | `/api/creators` | 列出创作者 |
| POST | `/api/creators/add` | 添加创作者来源 |
| POST | `/api/creators/fetch` | 抓取最近创作者视频 |
| POST | `/api/creators/enqueue` | 入队创作者视频 |
| GET | `/api/queue` | 读取队列状态和任务 |
| POST | `/api/queue/remove` | 移除队列任务 |
| POST | `/api/queue/run` | 运行队列任务 |

```text
clipvault/ui/static/index.html
clipvault/ui/static/app.js
clipvault/ui/static/style.css
```

前端 UI 文件。它们故意保持简单静态文件，没有前端构建步骤。

### 文档和日志

```text
docs/plan/roadmap.md
```

主项目路线图和阶段历史。

```text
docs/plan/phase6-ui-spec.md
```

桌面 UI 实现规格，包括本地安全边界和 job 模型。

```text
docs/plan/phase7-quality-and-docs.md
```

Phase 7 的质量和文档建设计划。

```text
logs/development/
```

按步骤记录开发日志，说明改了什么、为什么改、如何验证。

```text
logs/program/
```

程序日志约定，保持用户可见运行消息一致。

### 测试

```text
tests/
```

覆盖范围包括：

- 平台检测和 adapter。
- 字幕解析。
- 导出器。
- 仓库 helper 和索引重建。
- 系列规则。
- 创作者注册、抓取、入队。
- 队列执行。
- 认证和登录行为。
- CLI 参数解析。
- UI server helper 行为。

MVP review 时完整测试结果：

```text
271 passed
```

## CLI 表面

### 单视频

```powershell
clipvault video <url>
clipvault video <url> --series "Series Name"
clipvault video <url> --force
clipvault video <url> --device cuda --model small
clipvault video <url> --cookies
clipvault video <url> --cookies ".secrets\cookies.txt"
```

兼容旧式简写：

```powershell
clipvault <url>
```

### 仓库

```powershell
clipvault library rebuild-index
clipvault library rebuild-index --library "E:\VideoSubs"
clipvault library rebuild-index --dry-run
```

### 创作者

```powershell
clipvault creator add <creator-url> --name "Display Name"
clipvault creator list
clipvault creator fetch <creator-id-or-name> --limit 20
clipvault creator enqueue <creator-id-or-name> --limit 20
```

### 队列

```powershell
clipvault queue status
clipvault queue list
clipvault queue list --status pending
clipvault queue run --limit 1
clipvault queue run --limit 3 --retry-failed
```

### 认证

```powershell
clipvault auth login
clipvault auth list
clipvault auth logout
```

### UI

```powershell
clipvault ui
clipvault ui --port 8080
clipvault ui --no-open
clipvault ui --library "E:\VideoSubs"
```

## 数据文件

### 视频 Manifest

每个处理过的视频都有：

```text
manifest.json
```

重要字段：

- `schema_version`
- `platform`
- `source_url`
- `webpage_url`
- `video_id`
- `title`
- `uploader`
- `creator_id`
- `duration`
- `upload_date`
- `processed_at`
- `series`
- `subtitle_source`
- `asr_model`
- `asr_device`
- `output_files`

### 创作者索引

```text
library/<platform>/<creator>/_index.json
```

用于仓库浏览和未来 GUI/自动化功能。

### 系列索引

```text
library/<platform>/<creator>/<series>/_index.json
```

仅在系列目录中创建。

### 创作者注册表

```text
library/_creators.json
```

记录关注的创作者或频道来源。

### 队列

```text
library/_queue.json
```

记录 pending、done 和 failed 字幕任务。

### UI 设置

Windows：

```text
%APPDATA%\ClipVault\settings.json
```

其他系统：

```text
~/.config/ClipVault/settings.json
```

保存：

- `library`
- `model`
- `device`
- `compute_type`
- `cookies`

### 凭据

保存的认证：

```text
%APPDATA%\clipvault\auth.toml
```

生成的本地 Netscape cookies 缓存：

```text
%APPDATA%\clipvault\netscape_cookies.txt
```

这些文件是本地密钥，绝不能提交。

## 运行行为

单视频流程：

```text
URL
  -> yt-dlp metadata
  -> platform detection
  -> series resolution
  -> cache check
  -> platform subtitle / automatic caption lookup
  -> ASR fallback if no subtitle
  -> srt/txt/md export
  -> manifest update
  -> creator/series index update
```

UI 不复制管线逻辑。它启动 CLI 子进程，并通过 SSE 推送日志和结果。

## 手动验证状态

### YouTube

已验证：

```text
https://www.youtube.com/watch?v=Vdd6EOlRVbg
```

结果：

- Platform：`youtube`
- Creator：`Jabzy`
- Series：`History of the Middle East`
- Source：`automatic_caption:en-orig:json3`
- Segments：`983`
- Cache hit 也返回 `source` 和 `segments`

### Bilibili

已验证：

```text
https://www.bilibili.com/video/BV16G411973A
```

结果：

- Platform：`bilibili`
- Creator：`一条闲木鱼`
- Series：`大明王朝`
- Source：`asr:faster-whisper`
- Model/device：`small` + `cuda`
- Segments：`1290`
- 已保存 Bilibili 凭据可与 `--cookies` 配合使用

### Douyin

尝试过但不稳定：

```text
https://www.douyin.com/video/7609585779190612002
```

结果：

- `yt-dlp` 返回 `Fresh cookies are needed`。
- 当前已保存凭据只包含 Bilibili。
- 在可靠 cookies、登录或导出路径定义前，Douyin 仍应标记为 experimental。

## 已知限制

- Douyin 提取尚不稳定。
- UI 模型选择器可能展示本地未缓存的模型；缺模型时会清晰失败，但 UI 尚未展示已安装模型状态。
- 系列规则需要手动编辑 JSON，没有 UI 或 CLI 管理命令。
- 创作者追踪依赖平台 extractor 行为，平台页面变化可能影响结果。
- UI 可用但仍是 MVP，需要持续真实使用测试。
- 尚未实现 AI 笔记、问答、检索或知识库层。

## 未来开发方向

### 近期：产品打磨

1. 用真实视频高频使用，并记录 UX 问题。
2. 在 `docs/plan/` 维护结构化 issue 表。
3. 改善 UI 错误展示和空状态。
4. 展示已安装 ASR 模型，避免选择不可用模型。
5. 为系列规则增加 UI 控制。
6. 改善队列历史、重试可见性和 failed-job 诊断。

### 平台可靠性

1. 打磨 Bilibili 登录/session 刷新和字幕检测。
2. 用固定样本保持 YouTube 验证稳定。
3. 在声明支持前研究 Douyin cookies 和 extractor 可行性。
4. 增加常见失败模式的平台说明。

### 仓库管理

1. 更好的本地字幕搜索和过滤。
2. 从 UI 重命名或移动系列。
3. 重复检测和清理工具。
4. 导入/导出仓库元数据。
5. 旧布局迁移 helper。

### AI 层

仅在字幕获取和仓库浏览稳定后再做：

1. Transcript chunking。
2. 本地或 API 摘要。
3. Markdown 笔记生成。
4. 单个 transcript 问答。
5. 创作者/系列集合问答。
6. Claim extraction 和事实核查流程。

核心原则不变：字幕是耐久源资产，AI 笔记是派生资产。

## 交接说明

新开发者建议从这里开始：

1. `README.md`：使用方式。
2. `docs/plan/roadmap.md`：阶段上下文。
3. `clipvault/cli.py::process_video()`：主流程。
4. `clipvault/library.py`：存储、缓存和索引。
5. `clipvault/ui/server.py`：本地 API 和 job 执行。
6. `tests/test_cli.py`、`tests/test_library.py`、`tests/test_ui_server.py`：行为契约。

修改前建议执行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node --check clipvault\ui\static\app.js
git diff --check
```

真实链接验证使用 `docs/plan/roadmap.md` 中列出的样本，并记录准确 URL、结果、来源、segment count 和失败模式。
