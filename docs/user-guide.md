# ClipVault 用户手册

> Status: active
> Last updated: 2026-05-12
> Source of truth: 普通用户安装、配置和使用 ClipVault 的说明。

## 1. ClipVault 是什么

ClipVault 是一个本地优先的视频字幕库。它接收视频 URL，优先保存平台已经提供的字幕；如果平台没有字幕，就下载音频并运行本地 ASR，然后把结果稳定保存到本地仓库。

它的重点是：

- 可靠拿到字幕
- 把字幕长期保存到本地
- 让你能按平台、创作者、系列持续积累内容

它不是一个“自动生成 AI 笔记”的产品。当前重点仍然是字幕资产管理。

## 2. 安装（Windows）

### 前置要求

- 已安装 Python 3.10 及以上
- 已安装 `ffmpeg`，并且命令在 `PATH` 中可用

先确认 `ffmpeg`：

```powershell
ffmpeg -version
```

### 安装依赖

在项目根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
```

如果你使用 NVIDIA GPU，并希望本地 ASR 优先走 CUDA：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-gpu-win.lock
```

## 3. 快速开始：处理第一个视频

处理一个视频：

```powershell
.\clipvault.ps1 "https://www.bilibili.com/video/BV..."
```

如果平台有可用字幕，ClipVault 会直接保存平台字幕；如果没有，就会自动回退到本地 ASR。

处理完成后，输出通常位于：

```text
library/<platform>/<creator>/<video title - id>/
```

目录中会包含：

- `manifest.json`
- `transcript.srt`
- `transcript.txt`
- `transcript.md`

## 4. 常用命令

### 强制重处理

```powershell
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --force
```

### 保留下载音频

```powershell
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --keep-audio
```

### 指定 ASR 模型

```powershell
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --model tiny
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --model medium
```

### 指定设备

```powershell
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --device auto
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --device cuda
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --device cpu
```

### 指定计算类型

```powershell
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --compute-type auto
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --compute-type float16
```

### 中文转简

默认情况下，中文 ASR 结果会尝试从繁体转换为简体。如果你想保留原始输出：

```powershell
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --no-simplify-chinese
```

## 5. 系列归档

### 手动指定系列

```powershell
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --series "睡前消息"
```

这样视频会落到：

```text
library/<platform>/<creator>/<series>/<video title - id>/
```

### 自动系列规则

如果你没有传 `--series`，ClipVault 会尝试读取：

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
    }
  ]
}
```

显式 `--series` 永远优先于自动规则。

## 6. 登录与 Cookie

部分 Bilibili 视频、字幕或创作者页面需要登录态。

### 方式一：使用已保存凭据

先登录：

```powershell
clipvault auth login
```

之后可以直接写：

```powershell
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --cookies
```

### 方式二：使用 cookies.txt

```powershell
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --cookies ".secrets\\bilibili-cookies.txt"
```

ClipVault 只会记录 Cookie 文件路径，不会打印 Cookie 内容。

## 7. 仓库管理

### 重建索引

如果 `_index.json` 被删除、过期，或者你手动调整过仓库内容，可以重建：

```powershell
.\clipvault.ps1 library rebuild-index
```

只看计划，不写文件：

```powershell
.\clipvault.ps1 library rebuild-index --dry-run
```

### 旧缓存兼容

ClipVault 仍能复用旧版目录结构的缓存，但前提是：

- `manifest.json` 完整
- `transcript.srt`
- `transcript.txt`
- `transcript.md`

都存在且状态一致

## 8. 创作者与队列

### 添加创作者来源

```powershell
.\clipvault.ps1 creator add "https://www.youtube.com/@Jabzy" --name "Jabzy"
```

### 查看创作者列表

```powershell
.\clipvault.ps1 creator list
```

### 预览最近视频

```powershell
.\clipvault.ps1 creator fetch "Jabzy" --limit 10
```

### 把新视频加入队列

```powershell
.\clipvault.ps1 creator enqueue "Jabzy" --limit 10
```

### 查看队列

```powershell
.\clipvault.ps1 queue status
.\clipvault.ps1 queue list
```

### 执行队列

```powershell
.\clipvault.ps1 queue run --limit 1
.\clipvault.ps1 queue run --limit 3 --retry-failed
```

## 9. 本地 Web UI

启动界面：

```powershell
.\clipvault.ps1 ui
```

不自动打开浏览器：

```powershell
.\clipvault.ps1 ui --no-open
```

Web UI 包含：

- 视频处理
- 仓库浏览
- 创作者管理
- 队列查看和执行
- 设置保存

视频页和队列页都支持：

- 设备选择
- 模型选择
- 中文转简开关
- 实时日志
- 结果卡片
- 直接打开任务日志目录

设置页支持保存：

- 仓库路径
- Whisper 模型
- 设备
- 计算类型
- 中文转简默认值
- Cookie 文件路径

### 处理状态怎么看

ClipVault 现在会把任务状态明确写进 `manifest.json`：

- `processing_state: completed`：本次处理成功完成
- `processing_state: failed`：本次处理失败
- `last_error`：最后一次失败原因
- `failed_at`：失败时间

这能帮助你区分：

- 已完成的视频
- 正在处理中但中途失败、只留下半成品的目录

### 字幕来源怎么看

结果卡片和仓库详情会尽量把来源说清楚：

- `平台字幕（xx / fmt）`：直接使用平台字幕轨
- `平台自动字幕（xx / fmt）`：直接使用平台自动字幕轨
- `本地 ASR（faster-whisper）`：平台没有可下载字幕轨，已回退到本地 ASR

注意：

- 视频标题里写“中字”“双语”“中英字幕”，不代表平台一定提供了可下载字幕文件
- 很多时候那只是视频画面里的硬字幕，ClipVault 仍然会回退到 ASR

### 任务日志在哪里

Web UI 启动任务后，会显示“任务日志目录”，你也可以直接点击“打开任务日志”。

默认日志位置通常是：

```text
%APPDATA%\ClipVault\jobs\
```

如果默认目录不可写，程序会自动回退到：

```text
<你的字幕仓库>\_job_logs\
```

再不行时，会继续回退到工作目录下的：

```text
.tmp\jobs\
```

每个任务目录通常包含：

- `job.json`：任务状态、错误摘要、返回码、日志文件路径
- `stderr.log`：实时阶段日志和错误日志
- `stdout.txt`：CLI 最终标准输出
- `result.json`：成功任务的结果 JSON

## 10. 常见问题

### 1. 提示找不到 `ffmpeg`

说明系统 `PATH` 中没有可用的 `ffmpeg`。先安装 `ffmpeg`，再确认：

```powershell
ffmpeg -version
```

### 2. 平台字幕拿不到，为什么走了 ASR

这是正常回退逻辑。ClipVault 会优先尝试平台字幕；如果平台没有返回可用字幕，就自动回退到本地 ASR。

如果结果卡片写的是“本地 ASR”，就表示这次并没有拿到平台字幕轨。

### 3. 提示 Cookie 无效或页面仍然拒绝访问

优先检查：

- Cookie 文件是不是 Netscape 格式
- Cookie 是否新鲜
- 账号能否在浏览器里正常打开该视频
- `yt-dlp` 是否需要更新

### 4. CUDA 没生效

ClipVault 的默认行为是 `--device auto`。如果本机 CUDA 运行时不可用，它会自动回退到 CPU。你可以先试：

```powershell
.\clipvault.ps1 "https://www.bilibili.com/video/BV..." --device cuda
```

如果仍然回退，通常说明本机 GPU 运行时依赖未安装完整。

### 5. `transcript.md` 和 `transcript.txt` 有什么区别

- `transcript.txt` 更接近原始逐段语料，保留时间戳
- `transcript.md` 是更适合阅读的段落化正文

## 11. 适用范围说明

当前最稳定的路径仍然是：

- Bilibili
- YouTube

Douyin 仍然是原型支持，真实可用性依赖平台提取状态和新鲜 Cookie，不应当作稳定主路径使用。
