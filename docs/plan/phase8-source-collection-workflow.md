# Phase 8：合集与来源资产化摄取

> Status: planned
> Last updated: 2026-05-12
> Source of truth: Phase 8 合集/来源资产模型、批量摄取链路和验收标准。
> Supersedes: 旧的 `series` 字段作为唯一合集表达方式，以及 `_creators.json` 只登记创作者的局部模型。

## 背景

Phase 7 让单个视频字幕获取、Web UI 结果反馈和任务日志基本可用。下一步不应该继续把“合集”和“博主来源”当成单个视频处理时的附属字段，而是要把它们做成 ClipVault 的核心资产。

用户期望的产品模型是：

1. 输入一个 Bilibili 合集、播放列表或 UP 主主页。
2. ClipVault 先解析出一份完整视频清单。
3. 用户能看到每个视频的标题、状态和字幕获取情况。
4. 用户勾选其中一部分或全部视频，批量获取字幕。
5. 收藏夹里能打开这个合集或来源，随时查看哪些视频已下载字幕、哪些还没有。

这意味着 Phase 8 的核心不是“批量执行多个 URL”，而是“先创建合集/来源资产，再围绕这份资产逐步获取字幕”。

## 当前基线

### 已有能力

- 单视频处理已可用：`clipvault video <url>`。
- 手动系列归档已可用：`--series "Series Name"`。
- 创作者来源注册已可用：`clipvault creator add <url> --name ...`。
- 创作者预览已可用：`clipvault creator fetch <selector>`。
- 创作者入队已可用：`clipvault creator enqueue <selector>`。
- 队列执行已可用：`clipvault queue run --limit N`。
- Web UI 的“来源”模式当前可登记来源并检查最近视频。

### 当前不足

- Web UI 的“合集”模式仍是占位逻辑，没有真实解析和预览。
- 现有 `series` 只是视频目录归档字段，不能表示“一个合集里还有哪些视频未下载”。
- `_creators.json` 只登记创作者来源，不适合同时承载合集、播放列表和来源详情页。
- `_queue.json` 是执行队列，不是长期资产索引。
- 收藏夹里的“合集”只能从已下载视频反推，无法显示空合集或未下载视频。

## 产品目标

### 合集链路

用户粘贴 Bilibili 合集或 YouTube playlist 后：

1. ClipVault 解析合集信息和全部视频条目。
2. 系统创建一个本地合集资产，即使用户还没下载任何字幕，也能在收藏夹中看到它。
3. 合集详情页展示所有视频，按状态区分：
   - 未获取
   - 已入队
   - 处理中
   - 已完成
   - 失败
4. 用户可以勾选全部或部分视频，点击“获取所选字幕”。
5. 下载完成后，字幕文件进入该合集目录，视频状态自动更新。
6. 用户以后打开该合集，仍能看到完整视频列表和字幕状态。

### 来源链路

用户粘贴 UP 主主页或频道 URL 后：

1. ClipVault 创建一个来源资产。
2. 第一次检查时抓取最近视频列表。
3. 后续点击“检查更新”会追加新视频，不丢失旧视频状态。
4. 用户可以勾选新视频或失败视频，批量获取字幕。
5. 收藏夹的“来源”详情页展示该来源已发现的全部视频及字幕状态。

合集和来源的差别：

- 合集通常是相对固定的视频列表。
- 来源会持续变化，需要反复检查更新。

## 统一数据模型

Phase 8 建议新增统一的来源资产文件，而不是继续扩展 `_creators.json`。

建议文件：

```text
library/_sources.json
```

建议结构：

```json
{
  "schema_version": 1,
  "type": "source_registry",
  "updated_at": "2026-05-12T00:00:00Z",
  "sources": [
    {
      "id": "bilibili-playlist-xxxx",
      "source_type": "collection",
      "platform": "bilibili",
      "name": "大明王朝深度拆解",
      "source_url": "https://www.bilibili.com/...",
      "created_at": "2026-05-12T00:00:00Z",
      "last_checked_at": "2026-05-12T00:00:00Z",
      "item_count": 63,
      "completed_count": 12,
      "pending_count": 0,
      "failed_count": 1,
      "items": [
        {
          "id": "BV...",
          "url": "https://www.bilibili.com/video/BV...",
          "title": "第 63 回：...",
          "duration": 2730,
          "upload_date": "20260512",
          "order": 63,
          "status": "not_downloaded",
          "library_path": null,
          "subtitle_source": null,
          "queued_job_id": null,
          "last_error": null,
          "updated_at": "2026-05-12T00:00:00Z"
        }
      ]
    }
  ]
}
```

`source_type` 取值建议：

- `collection`：Bilibili 合集、YouTube playlist、本地系列。
- `creator`：UP 主主页、YouTube channel。

视频 `status` 取值建议：

- `not_downloaded`：已发现，但未获取字幕。
- `queued`：已加入字幕任务队列。
- `running`：正在处理。
- `completed`：字幕已归档。
- `failed`：处理失败。

## 仓库布局建议

已完成字幕仍然保持现有视频目录布局：

```text
library/<platform>/<creator>/<series>/<video title - id>/
```

Phase 8 不需要立刻改变字幕文件位置。新增 `_sources.json` 只负责记录“合集/来源资产”和“未下载视频列表”。

当 `source_type=collection` 且用户选择归档合集时：

- 下载单个视频时继续传入 `series=<source.name>`。
- 已完成视频仍写入现有系列目录。
- `_sources.json` 中对应 item 的 `library_path` 指向归档后的视频目录相对路径。

这样能保持向后兼容，又能表达空合集和未下载视频。

## 后端开发任务

### Step 1：新增 source registry 模块

建议新增：

```text
clipvault/sources.py
```

职责：

- 读取/写入 `library/_sources.json`。
- 创建或更新来源资产。
- 按 id、名称或 URL 查找来源资产。
- 合并新抓取的视频条目，保留已有 item 状态。
- 根据仓库 manifest/index 回填 item 的 `completed` 状态和 `library_path`。

### Step 2：统一解析合集和来源

复用 `yt-dlp` 的 playlist/channel 提取能力。

建议新增函数：

```python
parse_source_entries(url: str, *, limit: int | None, cookies: Path | None) -> ParsedSource
```

返回：

- `platform`
- `source_type`
- `name`
- `source_url`
- `items`

需要区分：

- playlist/合集 URL：尽量提取完整列表。
- creator/channel URL：默认限制最近 N 条，避免一次抓太多。

### Step 3：批量入队

新增能力：

- 将某个 source 的选中 item 加入 `_queue.json`。
- 队列 job 需要记录 `source_id` 和 `source_item_id`。
- `queue run` 成功或失败后回写 `_sources.json` 的 item 状态。

队列 job 建议扩展：

```json
{
  "id": "job-id",
  "status": "pending",
  "source_url": "https://...",
  "source_id": "bilibili-playlist-xxxx",
  "source_item_id": "BV...",
  "series": "大明王朝深度拆解"
}
```

### Step 4：Web API

建议新增或替换 API：

```text
GET  /api/sources
POST /api/sources/parse
POST /api/sources/refresh
POST /api/sources/enqueue
GET  /api/sources/<id>
```

语义：

- `parse`：用户粘贴 URL 后解析并创建/更新来源资产。
- `refresh`：重新检查已有来源，追加新视频。
- `enqueue`：把用户勾选的视频加入队列。
- `GET /api/sources`：收藏夹显示合集和来源。
- `GET /api/sources/<id>`：详情页显示完整视频列表。

### Step 5：前端页面

获取字幕模块：

- `合集` 模式接入真实解析。
- `来源` 模式改为同一套解析/刷新逻辑。
- 解析完成后展示视频清单，而不是只显示日志。
- 清单支持：
  - 全选
  - 只选未获取
  - 只选失败
  - 单项勾选
  - 获取所选字幕

收藏夹模块：

- `合集` 列表从 `_sources.json` 渲染 `source_type=collection`。
- `来源` 列表从 `_sources.json` 渲染 `source_type=creator`。
- 打开合集/来源时显示详情页：
  - 全部视频
  - 字幕状态
  - 字幕来源
  - 失败原因
  - 打开字幕
  - 重试

## 用户工作流

### 合集

1. 打开主页。
2. 切到“合集”。
3. 粘贴 Bilibili 合集链接。
4. 点击“解析合集”。
5. 查看视频列表。
6. 勾选需要获取字幕的视频。
7. 点击“获取所选字幕”。
8. 在收藏夹的“合集”中打开该合集，查看每个视频的字幕状态。

### 来源

1. 打开主页。
2. 切到“来源”。
3. 粘贴 UP 主主页或频道链接。
4. 点击“检查来源”。
5. 查看新视频列表。
6. 勾选需要获取字幕的视频。
7. 点击“获取所选字幕”。
8. 后续点击“检查更新”，追加新视频。

## 验收标准

### 合集验收

- 输入一个真实 Bilibili 合集 URL 后，页面显示视频列表。
- 列表中至少包含标题、URL、顺序、状态。
- 未下载的视频显示为“未获取”。
- 勾选 1-2 个视频后可以加入队列。
- 队列执行成功后，视频状态变为“已完成”。
- 收藏夹“合集”中能看到该合集，即使只下载了部分视频。
- 打开合集详情页能看到已下载和未下载视频混排。

### 来源验收

- 输入一个真实 UP 主主页后，页面显示最近视频列表。
- 已经下载过字幕的视频显示为“已完成”。
- 新视频显示为“未获取”。
- 点击“检查更新”不会清空旧状态。
- 勾选新视频后可以加入队列并处理。
- 收藏夹“来源”中能看到该来源和最近检查时间。

### 回归要求

- 单视频处理不能受影响。
- 现有 `--series` 仍可继续工作。
- 现有 `_creators.json` 可以保留读取兼容，但新功能应以 `_sources.json` 为主。
- 队列失败必须写入 item 的 `last_error`。
- 任何 cookies 路径可以记录，但绝不能记录 cookies 内容。

## 不在 Phase 8 范围内

- AI 摘要、问答、笔记生成。
- 云同步。
- 全文搜索数据库。
- 自动后台定时订阅。
- Douyin 稳定承诺。

这些可以在合集/来源资产模型稳定之后再进入后续阶段。

## 推荐实现顺序

1. 新增 `sources.py` 和 `_sources.json` schema。
2. 实现合集 URL 解析并创建 `collection` source。
3. 在 Web UI 合集模式展示解析后的条目列表。
4. 实现选中 item 入队。
5. 扩展 `queue run`，处理完成后回写 source item 状态。
6. 收藏夹合集列表改为读取 `_sources.json`。
7. 复用同一套机制实现 `creator` source。
8. 增加详情页和失败重试。
