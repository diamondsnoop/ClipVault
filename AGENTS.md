# ClipVault Agent 指南

## 项目目标

ClipVault 是一个本地优先的视频字幕库。当前优先级是可靠获取、保存和维护原始视频字幕，而不是生成 AI 笔记。

核心流程：

1. 接收视频 URL。
2. 优先使用平台字幕或自动字幕。
3. 没有字幕时下载音频并运行本地 ASR。
4. 导出 `srt`、`txt` 和 `md`。
5. 把输出保存到稳定的本地仓库路径。

## 当前范围

已实现：

- 通过 `yt-dlp` 处理 Bilibili URL。
- 通过 `yt-dlp` 验证 YouTube 字幕流程。
- 有平台字幕时优先提取字幕。
- 无字幕时下载音频。
- 使用 `faster-whisper` 本地 ASR。
- CUDA 自动选择，失败时回退 CPU。
- 本地文件输出：
  - `manifest.json`
  - `transcript.srt`
  - `transcript.txt`
  - `transcript.md`
- 平台感知的创作者/视频目录结构：
  - `library/<platform>/<creator>/<video title - id>/`
- 完整旧缓存目录兼容：
  - `library/<creator>/<video title - id>/`
- 本地 Web UI：
  - 视频处理
  - 仓库浏览
  - 创作者管理
  - 队列查看和执行
  - 设置保存

手动系列分组：

- `--series "Series Name"` 把视频放入系列目录。
- 路径：`library/<platform>/<creator>/<series>/<video title - id>/`。
- Manifest 写入 `"series": "Series Name"`。
- 这是手动指定，不是自动识别，也不是创作者订阅。

自动系列规则：

- 未传入 `--series` 时，ClipVault 读取 `library/<platform>/<creator>/_series_rules.json`。
- 支持基于标题的 `title_contains` 关键词列表或 `title_regex` 正则。
- 第一条匹配规则生效，按文件顺序执行。
- 显式 `--series` 永远优先于自动规则。
- 规则文件需要手动创建，目前没有 CLI 管理命令。
- 这是本地标题匹配，不是 AI 识别，也不是创作者订阅。

自动维护的仓库索引：

- `library/<platform>/<creator>/_index.json`：创作者索引，包含全部视频和系列聚合。
- `library/<platform>/<creator>/<series>/_index.json`：系列索引，仅在使用系列时创建。
- 新处理和缓存命中都会更新索引。
- 可通过 `clipvault library rebuild-index` 从完整 manifest 重建索引。
- 索引是普通 JSON，不需要数据库。

创作者来源注册：

- `library/_creators.json` 保存创作者/频道来源 URL，用于后续批量摄取。
- `clipvault creator add <url> --name "Display Name"` 记录或更新来源。
- `clipvault creator list` 打印已记录来源。
- `clipvault creator fetch <selector>` 预览来源的最近条目。
- fetch 条目包含 `library_status`，值为 `new` 或 `processed`。
- fetch 只做预览，不处理字幕，不入队 ASR 任务。
- `clipvault creator enqueue <selector>` 把 `new` 条目写入 `library/_queue.json`。
- `clipvault queue list/status/run` 查看并执行队列任务。
- `queue run` 默认一次执行一个 pending 任务，并调用现有视频处理流程。

认证平台访问：

- `--cookies` 不带值时使用 `clipvault auth login` 保存的凭据。
- `--cookies <path>` 使用本地 Netscape 格式 `cookies.txt` 文件。
- Cookies 会传给 `yt-dlp` 元数据提取、创作者抓取、音频下载和字幕 HTTP 下载。
- 支持命令：
  - `clipvault video <url> --cookies`
  - `clipvault creator fetch <selector> --cookies`
  - `clipvault creator enqueue <selector> --cookies`
  - `clipvault queue run --cookies`
- Cookie 文件是凭据。绝不能提交、记录、粘贴或暴露内容。

暂未实现或暂不稳定：

- YouTube/Douyin 平台专门打磨，当前主要依赖通用 `yt-dlp` 路径。
- 系列规则管理 CLI。
- 创作者自动订阅。
- 数据库或全文索引。
- AI 摘要、问答或笔记生成。
- Douyin 稳定支持。当前取决于 fresh cookies 和平台提取状态。

## 仓库结构

- `clipvault/cli.py`：CLI 入口和高层流程编排。
- `clipvault/adapters.py`：平台适配器注册、域名识别、字幕语言偏好、扁平条目 URL 补全。
- `clipvault/platforms.py`：通过 `yt-dlp` 提取 URL 元数据和下载音频。
- `clipvault/subtitles.py`：字幕轨选择、下载和解析。
- `clipvault/asr.py`：`faster-whisper`、CUDA/CPU 选择、本地模型解析。
- `clipvault/library.py`：文件命名、manifest、仓库路径、缓存、索引。
- `clipvault/series_rules.py`：基于标题的自动系列规则匹配。
- `clipvault/exporters.py`：导出 `srt`、`txt` 和 `md`。
- `clipvault/creators.py`：创作者注册、抓取预览、入队、队列状态。
- `clipvault/auth.py`、`clipvault/login.py`、`clipvault/credentials.py`：认证、登录和 cookies 凭据处理。
- `clipvault/ui/server.py`：本地 Web UI 服务、API、后台任务、SSE 日志。
- `clipvault/ui/static/`：无构建步骤的前端静态文件。
- `clipvault/models.py`：共享数据类。
- `clipvault/text.py`：文本清理工具。
- `clipvault.ps1`：Windows 开发启动脚本。
- `requirements.lock`：基础运行时依赖。
- `requirements-gpu-win.lock`：可选 Windows NVIDIA GPU 运行时依赖。
- `uv.lock`：uv 生成的锁定数据。

## 本地运行环境

项目使用本地 `.venv`，但 `.venv/` 被 git 忽略，不能提交。

安装基础依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
```

安装可选 Windows NVIDIA GPU 运行时：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-gpu-win.lock
```

`ffmpeg` 必须在 `PATH` 中可用。

## 常用命令

查看帮助：

```powershell
.\clipvault.ps1 --help
```

处理视频：

```powershell
.\clipvault.ps1 "https://www.bilibili.com/video/BV..."
```

强制重新处理：

```powershell
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --force
```

归入系列：

```powershell
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --series "睡前消息"
```

使用 Bilibili 登录 cookies：

```powershell
clipvault auth login
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --cookies
```

使用显式 cookies 文件：

```powershell
mkdir .secrets
# 从浏览器导出 Netscape 格式 cookies.txt 并保存到：
# .secrets\bilibili-cookies.txt
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --cookies ".secrets\bilibili-cookies.txt"
```

强制 CPU：

```powershell
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --device cpu
```

启动本地 Web UI：

```powershell
.\clipvault.ps1 ui
.\clipvault.ps1 ui --no-open
```

验证 Python 依赖：

```powershell
.\.venv\Scripts\python.exe -m pip check
```

编译模块：

```powershell
.\.venv\Scripts\python.exe -m compileall clipvault
```

运行测试：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

只重建本地索引，不下载、不转写：

```powershell
.\clipvault.ps1 library rebuild-index
.\clipvault.ps1 library rebuild-index --dry-run
```

记录、抓取和入队创作者来源：

```powershell
.\clipvault.ps1 creator add "https://www.youtube.com/@Jabzy" --name "Jabzy"
.\clipvault.ps1 creator list
.\clipvault.ps1 creator fetch "Jabzy" --limit 10
.\clipvault.ps1 creator enqueue "Jabzy" --limit 10
.\clipvault.ps1 queue status
.\clipvault.ps1 queue run --limit 1
.\clipvault.ps1 creator fetch "闲木鱼" --cookies
.\clipvault.ps1 queue run --limit 1 --cookies
```

## 手动平台样本

开发任务需要真实平台验证时使用这些样本。不要让普通单元测试依赖这些链接或创作者，因为平台页面、字幕和访问规则会变化。

- Bilibili 主样本：闲木鱼《大明王朝》系列。
- Bilibili 次样本：马督公《睡前消息》系列。保留作为后续回归检查样本。
- YouTube：Jabzy，`History of the Middle East` 系列。
- Douyin：曾章见真章《曾章见真章创建的合集》系列。

真实样本验证时，在 `logs/development/` 记录准确 URL、日期、字幕来源（平台字幕或 ASR）、输出路径和平台特定失败。

## 开发规则

- 项目聚焦字幕获取和字幕库维护。
- 在字幕获取和仓库管理稳定前，不添加 AI 笔记生成。
- 不提交生成字幕、音频文件、模型缓存、`.venv/` 或包缓存。
- 不提交 `.secrets/`、`cookies.txt`、`*.cookies.txt` 或任何导出的登录凭据。
- GPU 运行时保持可选，不强迫所有用户安装大型 NVIDIA 包。
- 除非明确改变行为，否则保持现有 CLI 行为稳定。
- 优先使用小而可测试的模块，不继续把逻辑堆进 `cli.py`。
- 文档和生成文本使用 UTF-8。
- 每个开发任务都要围绕明确目标逐步执行。完成有意义的步骤后，在 `logs/development/` 写对应开发日志。
- 代码变更应在合适位置提供用户可见程序日志。功能应该报告正在做什么、成功了什么、失败了什么，并提供足够诊断上下文。程序日志规范和示例放在 `logs/program/`。
- 缓存复用必须基于完整 manifest 状态和实际字幕文件，不能只看单个 marker 字段或 `transcript.md`。
- ASR 当前只使用本地模型文件。除非自动下载模型已实现并验证，否则不要写暗示 ClipVault 会自动下载模型的用户文案。

## 日志

ClipVault 把日志视为长期维护材料，不是临时备注。

### 开发日志

开发日志目录：

```text
logs/development/
```

开发日志用于记录项目如何变化。每个开发任务应创建或更新一个日期 Markdown 文件。推荐命名：

```text
logs/development/YYYY-MM-DD-short-topic.md
```

每条记录应包含：

- Target：任务的具体目标。
- Steps：计划步骤和完成情况。
- Changes：重要变更文件。
- Verification：执行的命令、场景和结果。
- Follow-ups：未解决问题或推荐后续任务。

### 程序日志

程序日志规范目录：

```text
logs/program/
```

程序日志关注运行时可观测性。新增或修改代码时，确保用户能理解：

- 正在运行哪个阶段，例如元数据提取、字幕查找、音频下载、ASR、导出或缓存复用。
- 成功了什么，例如字幕来源、ASR 设备/模型、输出路径和有用的耗时。
- 失败了什么，例如操作、错误原因和实际排查建议。
- 是否正在回退，例如 CUDA 到 CPU、平台字幕到 ASR。
- 是否启用了认证访问，但绝不能打印 cookie 内容。

当前 CLI 可以继续使用简单 stderr/stdout 消息。随着 ClipVault 成长，优先演进到结构化日志层，以便未来支持 GUI 进度、日志文件和 bug 报告。

## 开源维护标准

把 ClipVault 当作长期、专业、友好的开源项目维护：

- 避免只在单台机器上有效的一次性本地 hack。
- 记录配置、依赖假设和平台特定行为。
- 优先维护清晰接口，而不是快速耦合。
- 让非作者用户也能理解失败。
- 除非有意改变并记录，否则保持公开行为稳定。
- 留下足够测试、日志和文档，让未来贡献者能安全继续开发。

## Git 卫生

已忽略的本地和运行时目录包括：

- `.venv/`
- `.secrets/`
- `.pip-cache/`
- `.uv-cache/`
- `.tmp/`
- `library/`
- `vendor/wheels/`
- `cookies.txt`
- `*.cookies.txt`

提交前建议执行：

```powershell
Remove-Item -LiteralPath clipvault\__pycache__ -Recurse -Force -ErrorAction SilentlyContinue
.\clipvault.ps1 --help
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q
node --check clipvault\ui\static\app.js
git status --short --ignored
```

## 近期路线

推荐下一步：

1. 根据真实 Bilibili 使用情况补充聚焦回归记录和测试。
2. 修复 Phase 7 记录的输出质量、JSON 防御和 UI 日志体验问题。
3. 增加面向普通用户的中文使用手册。
4. 展示本地已安装 ASR 模型，避免 UI 选择不存在模型。
5. 给系列规则增加 UI 或 CLI 管理能力。
6. 在字幕获取和仓库管理继续稳定前，继续把 AI 笔记生成放在后续阶段。
