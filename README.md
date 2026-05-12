# ClipVault

ClipVault 是一个本地优先的视频字幕库。它接收视频 URL，优先获取平台已有字幕或自动字幕；如果没有可用字幕，就下载音频并使用本地 ASR 转写；最后把 `srt`、`txt`、`md` 和 `manifest.json` 保存到稳定的本地仓库目录。

当前项目重点是“可靠获取和维护原始字幕资产”，不是 AI 笔记工具。Bilibili 是主要验证路径，YouTube 已通过同一套 `yt-dlp` 字幕流程验证。Douyin 目前只保留原型支持，实际可用性取决于平台访问和 cookies 状态。

## 当前能力

- 输入单个视频 URL 并处理字幕。
- 优先使用平台字幕或自动字幕。
- 没有字幕时回退到 `faster-whisper` 本地 ASR。
- 支持把中文 ASR 结果默认转换为简体中文，也可显式关闭。
- 自动选择 CUDA，失败时回退 CPU。
- 导出 `transcript.srt`、`transcript.txt`、`transcript.md`。
- 保存 `manifest.json`，用于缓存、索引和 UI 浏览。
- 按 `library/<platform>/<creator>/<video title - id>/` 组织本地仓库。
- 支持手动 `--series` 和本地标题规则 `_series_rules.json`。
- 自动维护创作者索引和系列索引。
- 支持创作者来源登记、最近视频预览、入队和队列执行。
- 提供本地 Web UI：视频处理、仓库浏览、创作者、队列、设置。

## 快速开始

创建虚拟环境并安装项目：

```powershell
cd "E:\myproject\ClipVault"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e .
```

如果需要可复现的固定依赖环境，先安装锁定文件：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
```

系统需要单独安装 `ffmpeg`，并确保它在 `PATH` 中：

```powershell
ffmpeg -version
```

处理一个视频：

```powershell
.\clipvault.ps1 "https://www.bilibili.com/video/BV..."
```

也可以直接调用 Python 模块：

```powershell
.\.venv\Scripts\python.exe -m clipvault "https://www.bilibili.com/video/BV..."
```

启动本地 Web UI：

```powershell
.\clipvault.ps1 ui
```

如果不想自动打开浏览器：

```powershell
.\clipvault.ps1 ui --no-open
```

UI 默认只监听 `127.0.0.1`，并使用启动时生成的一次性 token 保护本地 API。

## Bilibili 登录 Cookies

部分 Bilibili 视频、字幕、创作者页面或较高质量媒体需要登录态。ClipVault 支持两种 cookies 用法。

### 方式一：扫码登录（推荐）

```powershell
clipvault auth login
```

用 Bilibili App 扫码。凭据会保存在：

```text
%APPDATA%\clipvault\auth.toml
```

之后传入不带值的 `--cookies` 即可使用已保存凭据：

```powershell
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --cookies
.\clipvault.ps1 creator fetch "闲木鱼" --cookies
.\clipvault.ps1 queue run --limit 1 --cookies
```

### 方式二：手动 cookies.txt 文件

从浏览器导出 Netscape 格式 cookies，然后传入文件路径：

```powershell
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --cookies ".secrets\bilibili-cookies.txt"
.\clipvault.ps1 creator fetch "闲木鱼" --cookies ".secrets\bilibili-cookies.txt"
.\clipvault.ps1 queue run --limit 1 --cookies ".secrets\bilibili-cookies.txt"
```

Cookie 文件包含账号登录状态。不要分享、粘贴到 issue、写入日志或提交到 git。项目已忽略 `.secrets/`、`cookies.txt` 和 `*.cookies.txt`。

## Windows NVIDIA GPU

ClipVault 默认使用 `--device auto`，当 CTranslate2 可用 CUDA 时优先走 GPU，否则回退 CPU。Windows NVIDIA GPU 用户可以安装可选运行时：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-gpu-win.lock
```

GPU 依赖单独放在 `requirements-gpu-win.lock`，因为 NVIDIA wheel 体积较大。不需要 GPU 时可以跳过。

强制 CPU 或 CUDA：

```powershell
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --device cpu
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --device cuda
```

## 输出结构

默认输出到本地 `library/`：

```text
library/
  bilibili/
    Creator Name/
      _index.json
      Video Title - BVxxxx/
        manifest.json
        transcript.srt
        transcript.txt
        transcript.md
        source_audio.m4a        # 仅 --keep-audio 时保留
      Series Name/
        _index.json
        Video Title - BVxxxx/
          ...
```

传入 `--series "Series Name"` 后，路径变为：

```text
library/<platform>/<creator>/<series>/<video title - id>/
```

每次成功处理或命中完整缓存后，ClipVault 都会自动维护：

- 创作者索引：`library/<platform>/<creator>/_index.json`
- 系列索引：`library/<platform>/<creator>/<series>/_index.json`

索引是普通 JSON 文件，不需要数据库。旧版 `library/<creator>/<video title - id>/` 缓存目录在 manifest 和输出文件完整时仍可复用。

如果索引被删除、过期或不一致，可以从已有完整 manifest 重建：

```powershell
.\clipvault.ps1 library rebuild-index
.\clipvault.ps1 library rebuild-index --library "E:\VideoSubs"
.\clipvault.ps1 library rebuild-index --library "E:\VideoSubs" --dry-run
```

`rebuild-index` 只做本地维护，不下载视频、不抓字幕、不运行 ASR。

## 常用命令

```powershell
# 查看帮助
.\clipvault.ps1 --help

# 处理视频
.\clipvault.ps1 "https://www.bilibili.com/video/BV..."

# 即使已有完整缓存也重新处理
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --force

# 使用自定义仓库目录
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --library "E:\VideoSubs"

# 手动归入系列
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --series "睡前消息"

# 使用已保存登录凭据
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --cookies

# 使用指定 cookies 文件
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --cookies ".secrets\bilibili-cookies.txt"

# 使用较小 ASR 模型
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --model tiny

# 关闭中文 ASR 结果转简
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --no-simplify-chinese

# 启动本地 Web UI
.\clipvault.ps1 ui

# 重建创作者和系列索引
.\clipvault.ps1 library rebuild-index
```

## 自动系列规则

如果没有传入 `--series`，ClipVault 可以根据本地标题规则自动归类系列。规则文件位于：

```text
library/<platform>/<creator>/_series_rules.json
```

示例：

```json
{
  "schema_version": 1,
  "rules": [
    {
      "series": "睡前消息",
      "title_contains": ["睡前消息"],
      "title_regex": null
    },
    {
      "series": "History of the Middle East",
      "title_contains": ["History of the Middle East"],
      "title_regex": null
    }
  ]
}
```

规则说明：

- `title_contains`：标题包含任意一个字符串即匹配，区分大小写。
- `title_regex`：可选正则表达式，通过 `re.search` 匹配。
- 第一条匹配规则生效，规则按文件顺序执行。
- 规则文件需要手动创建，目前没有 CLI 管理命令。
- 显式传入的 `--series` 优先级永远高于自动规则。
- 这是本地标题匹配，不是 AI 识别，也不是创作者订阅。

## 创作者追踪和队列

记录创作者或频道来源：

```powershell
.\clipvault.ps1 creator add "https://www.youtube.com/@Jabzy" --name "Jabzy"
.\clipvault.ps1 creator list
```

预览最近视频：

```powershell
.\clipvault.ps1 creator fetch "Jabzy" --limit 10
```

`creator fetch` 只做预览，会根据本地完整 manifest 标记每条视频为 `new` 或 `processed`，不会处理字幕，也不会自动入队。

把新视频写入本地队列：

```powershell
.\clipvault.ps1 creator enqueue "Jabzy" --limit 10
```

队列文件位于：

```text
library/_queue.json
```

查看和执行队列：

```powershell
.\clipvault.ps1 queue status
.\clipvault.ps1 queue list --status pending
.\clipvault.ps1 queue run --limit 1
```

`queue run` 默认一次只跑一个 pending 任务，避免意外批量下载或长时间 ASR。失败任务可用 `--retry-failed` 显式重试。

## 本地 Web UI

Web UI 是现有 CLI 和核心流程的本地外壳，不重写业务逻辑。

```powershell
.\clipvault.ps1 ui
.\clipvault.ps1 ui --port 8080
.\clipvault.ps1 ui --no-open
.\clipvault.ps1 ui --library "E:\VideoSubs"
```

主要页面：

- 视频：输入 URL，选择模型、设备、系列、force、keep audio，查看实时日志和结果。
- 仓库：按平台、创作者、系列浏览本地字幕，预览 transcript。
- 创作者：添加来源、抓取最近视频、入队新视频。
- 队列：查看任务状态、移除任务、运行队列并查看日志。
- 设置：保存仓库路径、ASR 模型、设备和 cookies 路径。

## 开发验证

常用检查：

```powershell
.\clipvault.ps1 --help
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q
node --check clipvault\ui\static\app.js
git diff --check
```

真实平台验证不要写进默认单元测试。使用 Bilibili、YouTube、Douyin 等真实链接时，请记录 URL、日期、字幕来源、输出路径、片段数和失败模式到 `logs/development/`。

## 仓库卫生

不要提交生成数据、账号凭据或本地运行目录：

- `.venv/`
- `.secrets/`
- `.pip-cache/`
- `.uv-cache/`
- `.tmp/`
- `library/`
- `vendor/wheels/`
- `cookies.txt`
- `*.cookies.txt`
- 生成字幕、音频和模型缓存
