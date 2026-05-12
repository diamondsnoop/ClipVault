# Phase 6: Desktop UI — Implementation Spec

> Status: completed
> Last updated: 2026-05-12
> Source of truth: Phase 6 桌面 Web UI 的历史实现规格。
> Superseded by: Phase 7 Web UI 体验改造和当前 `clipvault/ui/static/` 实现。

## Overview

Build a local web-based GUI for ClipVault. The UI runs in the browser, powered by a lightweight Python web server. The frontend talks to local API endpoints; the server reuses existing `clipvault` behavior instead of reimplementing transcript logic. No frontend build step.

Execution model:

- Short local operations may call existing Python functions directly, such as listing creators, reading indexes, or rebuilding library indexes.
- Long-running transcript jobs must run through a background job manager. For video processing and queue execution, prefer launching the existing CLI in a subprocess so stderr logs can be streamed without global `stderr` redirection.
- The UI is a thin shell over the existing CLI/core pipeline. CLI behavior must remain fully supported.

## Architecture

```
clipvault/ui/                  # 新增模块
  ├── __init__.py
  ├── server.py                # 本地 Web 服务器
  └── static/
      ├── index.html           # 主界面 (SPA)
      ├── style.css            # 样式
      └── app.js               # 前端逻辑
```

启动方式：

```powershell
python -m clipvault ui        # 启动服务器，自动打开浏览器
python -m clipvault ui --port 9090 --no-open
```

默认 `http://127.0.0.1:8080`。服务只绑定 `127.0.0.1`，不监听 `0.0.0.0`。修改 `static/` 下任何文件 → 刷新浏览器即生效。

## 后端 Server (`server.py`)

使用 Python 标准库，**零额外依赖**。必须使用 `http.server.ThreadingHTTPServer`，因为 SSE 长连接会占用请求处理线程；普通 `HTTPServer` 会让日志流阻塞其他 API 请求。

不要引入 Flask/FastAPI/前端框架。Phase 6 的目标是一个可维护的本地工具壳，不是 Web 服务框架迁移。

### 安全边界

本地 UI 可以读取字幕、保存设置、打开本地目录、运行下载和 ASR，因此必须显式限制权限：

1. **绑定地址**：默认只监听 `127.0.0.1`。不提供 `0.0.0.0` 监听入口，除非未来单独设计远程访问安全方案。
2. **随机 token**：server 启动时生成一次性随机 token。自动打开浏览器时使用带 token 的本地 URL，例如：

   ```text
   http://127.0.0.1:8080/?token=<random-token>
   ```

   前端读取 token 后，所有 API 请求都带：

   ```text
   X-ClipVault-Token: <random-token>
   ```

3. **写操作校验**：所有 `POST` 接口、任务执行接口、设置保存接口、打开路径接口都必须校验 `X-ClipVault-Token`。
4. **Origin/Host 校验**：
   - `Host` 只允许 `127.0.0.1:<port>` 或 `localhost:<port>`。
   - `Origin` 为空时允许；存在时必须是同一个本地 origin。
5. **路径安全**：
   - 读取 transcript、打开文件夹、读取索引时，目标路径必须 `resolve()` 后仍在当前 configured library root 内。
   - 禁止接受任意绝对路径读取文件。
   - Cookie 文件路径只作为配置值传给后端任务，不读取内容给前端展示。
6. **凭证安全**：
   - UI 可以保存 Cookie 文件路径，但不能保存 Cookie 内容。
   - API 响应、日志、错误信息不得包含 Cookie 内容。

### 设置存储

设置保存到用户级本地配置文件，不提交进仓库：

- Windows: `%APPDATA%\ClipVault\settings.json`
- 其他系统: `~/.config/clipvault/settings.json`

首版设置字段：

```json
{
  "library": "E:\\myproject\\ClipVault\\library",
  "model": "small",
  "device": "auto",
  "compute_type": "auto",
  "cookies": ".secrets\\bilibili-cookies.txt"
}
```

保存的是 Cookie 文件路径，不是 Cookie 内容。

### 需要暴露的 API 端点

| 端点 | 方法 | 功能 | 对应后端函数 |
|---|---|---|---|
| `POST /api/video` | POST | 启动单视频处理任务 | 后台 job manager + `python -m clipvault video ...` 子进程 |
| `GET /api/process/status` | GET | 获取指定 job 状态 | 内存 job registry |
| `GET /api/process/events` | GET | 获取指定 job 实时日志 | SSE 推送 job events |
| `GET /api/library` | GET | 获取仓库树（平台→创作者→系列→视频） | 扫描 `library/` 目录 + `_index.json` |
| `GET /api/library/transcript` | GET | 获取指定视频的字幕文本 | 读取 `transcript.md` |
| `GET /api/creators` | GET | 列出已注册创作者 | `creators.list_creator_sources()` |
| `POST /api/creators/add` | POST | 添加创作者源 | `creators.add_creator_source()` |
| `POST /api/creators/fetch` | POST | 获取创作者最新视频预览 | `creators.fetch_creator_videos()` |
| `POST /api/creators/enqueue` | POST | 入队待处理视频 | `creators.enqueue_creator_videos()` |
| `GET /api/queue` | GET | 查看队列状态/列表 | `creators.queue_status()`, `creators.list_queue_jobs()` |
| `POST /api/queue/run` | POST | 启动队列执行任务 | 后台 job manager + `python -m clipvault queue run ...` 子进程 |
| `POST /api/library/rebuild-index` | POST | 重建索引 | `library.rebuild_library_indexes()` |
| `GET /api/settings` | GET | 获取当前配置 | library 路径、ASR model/device |
| `POST /api/settings` | POST | 更新配置 | 保存到用户配置文件 |
| `POST /api/open-path` | POST | 打开输出目录或仓库目录 | `os.startfile()` 等本机打开方式，路径限制在 library 内 |

### 流式日志（关键设计）

视频处理可能耗时较长（尤其是 ASR），前端需要实时看到处理进度。

方案：处理视频时启动后台 job，job 内部运行 CLI 子进程。stderr 日志逐行记录到 job events，并通过 SSE (Server-Sent Events) 推送到前端。stdout 的最终 JSON 解析为 job result。

```
POST /api/video  → 启动后台 job，返回 job_id
GET  /api/process/status?job_id=xxx  → 返回 job 状态/result/error
GET  /api/process/events?job_id=xxx  → SSE 流，每行日志作为一个事件推送
```

日志格式保持现有规范：`[pipeline]`、`[metadata]`、`[subtitle]`、`[asr]`、`[audio]`、`[export]` 前缀。

### Job 生命周期

首版只允许一个长任务运行，避免多个 ASR/下载任务互相抢 GPU、网络和文件写入：

- 如果已有 `running` job，新的 `POST /api/video` 或 `POST /api/queue/run` 返回 `409 busy`。
- job 状态：
  - `queued`
  - `running`
  - `succeeded`
  - `failed`
- job 数据：
  - `job_id`
  - `type`: `video` 或 `queue`
  - `status`
  - `command`
  - `created_at`
  - `started_at`
  - `finished_at`
  - `events`: stderr 日志行数组
  - `result`: CLI stdout JSON（成功时）
  - `error`: 失败摘要
  - `returncode`

SSE 事件类型：

- `log`: 一行 stderr 日志。
- `result`: 最终 JSON result。
- `error`: 任务失败。
- `done`: 任务结束。

## UI 设计

### 设计语言

严格按照 `DESIGN.md` 的 Anthropic 设计系统：

| Token | 值 | 用途 |
|---|---|---|
| `canvas` | `#faf9f5` | 页面主背景 — 暖调奶油色 |
| `primary` | `#cc785c` | 珊瑚色 — 主要操作按钮、重点高亮 |
| `primary-active` | `#a9583e` | 按钮悬停/按下态 |
| `surface-card` | `#efe9de` | 卡片背景 |
| `surface-dark` | `#181715` | 深色背景（代码展示、页脚） |
| `ink` | `#141413` | 主文字色 |
| `body` | `#3d3d3a` | 正文色 |
| `muted` | `#6c6a64` | 次要文字 |
| `hairline` | `#e6dfd8` | 边框分隔线 |
| `success` | `#5db872` | 成功状态 |
| `error` | `#c64545` | 错误状态 |

字体：display 用 Copernicus/Tiempos Headline（衬线），正文/UI 用 StyreneB/Inter（无衬线），回退用系统字体。

### 页面布局

```
┌─────────────────────────────────────────────────────┐
│ 导航栏 (top-nav)  64px                              │
│  ClipVault  [视频]  [仓库]  [创作者]  [队列]  [设置] │
├─────────────────────────────────────────────────────┤
│                                                     │
│  主内容区域                                         │
│                                                     │
│  (根据当前标签页切换)                                │
│                                                     │
│  - 视频页面: URL 输入框 + 处理按钮 + 实时日志区      │
│  - 仓库页面: 平台/创作者/系列树 + 字幕预览           │
│  - 创作者: 列表 + 新增表单 + 抓取/入队按钮          │
│  - 队列: 状态概览 + 列表 + 运行按钮                 │
│  - 设置: 配置表单                                    │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 页面详细设计

#### 1. 视频处理页 (默认首页)

```
┌────────────────────────────────────────────────────┐
│ [标题] 处理新视频                                    │
│                                                     │
│ ┌──────────────────────────────────────────────────┐│
│ │ 视频 URL 输入框                    [处理 (珊瑚)] ││
│ └──────────────────────────────────────────────────┘│
│  □ --series "系列名称"                              │
│  □ --force (强制重新处理)                          │
│  □ --device [auto ▼]                               │
│                                                     │
│ ┌──────────────────────────────────────────────────┐│
│ │ 处理日志 (实时 SSE 流)                           ││
│ │ [pipeline] processing video...                   ││
│ │ [metadata] extracting metadata...                 ││
│ │ [subtitle] checking platform subtitles...        ││
│ │ ...                                               ││
│ │ ───────────────────────────────────── 进度条 ───  ││
│ └──────────────────────────────────────────────────┘│
│                                                     │
│ 处理完成后显示结果卡片:                              │
│ ┌── 结果卡片 ──────────────────────────────────────┐│
│ │ ✅ status: ok  │ source: platform  │ ...         ││
│ │ [查看字幕] [打开输出目录]                         ││
│ └──────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

#### 2. 仓库浏览页

```
┌────────────────────────────────────────────────────┐
│ [标题] 字幕仓库                                      │
│                                                     │
│ ┌──────────────┐ ┌────────────────────────────────┐│
│ │ 侧边栏 (导航) │ │ 主内容                         ││
│ │              │ │                                 ││
│ │  ▼ bilibili  │ │ # 标题: 大明王朝...             ││
│ │    闲木鱼    │ │ 创作者: 一条闲木鱼              ││
│ │    大明王朝  │ │ 平台: bilibili                  ││
│ │      BV1...  │ │ 系列: 大明王朝                  ││
│ │      BV2...  │ │ 时长: 1991s                     ││
│ │    睡前消息  │ │ 处理日期: 2026-05-05            ││
│ │  ▼ youtube   │ │ 字幕来源: asr:faster-whisper   ││
│ │    Jabzy     │ │                                 ││
│ │              │ │ ┌── 字幕内容 ──────────────────┐││
│ │  [重建索引]  │ │ │ (transcript.md 内容)         │││
│ │              │ │ │ 你可以真的看懂了吗？...       │││
│ │              │ │ └──────────────────────────────┘││
│ └──────────────┘ └────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

侧边栏按层级展开：平台 → 创作者 → 系列 → 视频 ID。数据来源为 `_index.json`。

右侧点击视频后显示完整元数据 + transcript.md 内容预览。

#### 3. 创作者页

```
┌────────────────────────────────────────────────────┐
│ [标题] 创作者管理                                    │
│                                                     │
│ ┌── 添加创作者 ────────────────────────────────────┐│
│ │ URL: [________________]  名称: [________] [添加] ││
│ └──────────────────────────────────────────────────┘│
│                                                     │
│ ┌── 创作者列表 ────────────────────────────────────┐│
│ │ 闲木鱼 (bilibili)   [抓取] [入队]                ││
│ │   └─ 发现 15 个视频: 12 new, 3 processed         ││
│ │ Jabzy (youtube)      [抓取] [入队]                ││
│ └──────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

#### 4. 队列页

```
┌────────────────────────────────────────────────────┐
│ [标题] 任务队列                                      │
│                                                     │
│ 状态: 12 pending · 3 running · 45 done · 2 failed  │
│                                                     │
│ [运行队列 (limit: 1)]  [重试失败]                    │
│                                                     │
│ ┌── 队列列表 ──────────────────────────────────────┐│
│ │ # | 状态    | 视频标题         | 创作者  | 错误   ││
│ │ 1 | pending | 大明王朝 第一回  | 闲木鱼 |        ││
│ │ 2 | running | 大明王朝 第二回  | 闲木鱼 |        ││
│ │ 3 | done    | 大明王朝 第三回  | 闲木鱼 |        ││
│ │ 4 | failed  | 大明王朝 第四回  | 闲木鱼 | 超时   ││
│ └──────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

#### 5. 设置页

```
┌────────────────────────────────────────────────────┐
│ [标题] 设置                                          │
│                                                     │
│ 仓库路径: [/path/to/library]        [打开]          │
│ ASR 模型: [small ▼]                                │
│ 设备:     [auto ▼]                                 │
│ Cookie 文件路径: [/path/to/cookies]                │
│                                                     │
│ [保存设置]                                           │
└─────────────────────────────────────────────────────┘
```

浏览器不能可靠地打开系统文件夹选择器，也不能直接打开 Explorer/Finder。因此：

- 仓库路径和 Cookie 文件路径首版都使用文本输入。
- “打开输出目录”和“打开仓库目录”通过 `POST /api/open-path` 交给本地 server 执行。
- `POST /api/open-path` 必须校验 token，并且只允许打开 configured library root 内的路径。
- 不能把任意用户输入路径直接传给 `os.startfile()`。

## 实现边界

### 必须做的

1. 创建 `clipvault/ui/` 目录结构
2. `server.py` — 实现 `ThreadingHTTPServer`、安全 token、Origin/Host 校验、API 端点、SSE 流式日志、静态文件服务
3. `index.html` — SPA 单页，5 个标签页（视频、仓库、创作者、队列、设置）
4. `style.css` — 按 DESIGN.md 设计系统完整实现（所有颜色/圆角/字体/间距/卡片/按钮）
5. `app.js` — 前端路由、API 调用、SSE 消费、DOM 操作
6. CLI 入口：`clipvault ui` 子命令（在 `cli.py` 注册）
7. 调用现有后端函数，不重写任何业务逻辑
8. 实时开发体验：修改 `static/` 文件 → 刷新浏览器即生效
9. 长任务必须进入 job manager，不在 HTTP 请求线程里同步跑完
10. 路径读取和打开必须限制在 configured library root 内

### 绝对不做

1. **不增加新依赖** — 只用 Python 标准库 (`http.server`, `json`, `asyncio` 等)
2. **不引入前端框架** — 原生 HTML + CSS + JS。不写 React/Vue/Svelte
3. **不修改现有业务逻辑** — UI 只调用，不改动 `clipvault/` 核心模块
4. **不做浏览器自动化测试** — 视觉和交互先手动验证；但 server/helper/API 层必须有基础测试或 smoke tests
5. **不做 AI 功能** — 不生成摘要、问答、笔记
6. **不做云同步/登录/多用户** — 纯本地工具
7. **不写构建步骤** — 没有 webpack/vite/打包。直接 Serve 静态文件

### 响应式要求

- 桌面优先（1024px+ 是主要使用场景）
- 在 768px+ 下保持可用即可
- 不需要移动端适配

## 开发步骤

### Step 1: 骨架搭建
- 创建 `clipvault/ui/__init__.py`, `server.py`
- 注册 `ui` 子命令到 `cli.py`
- 实现最小 `server.py`：启动 `ThreadingHTTPServer`，绑定 `127.0.0.1`，Serve `index.html`
- 生成随机 token，自动打开 `http://127.0.0.1:<port>/?token=<token>`
- 实现 Host/Origin/token 校验工具函数
- 验证：`python -m clipvault ui` → 浏览器打开 → 看到页面；`--no-open` 时终端打印带 token 的 URL
- 测试：至少覆盖 token 校验、Host/Origin 校验、路径 root 限制 helper

### Step 2: 基础前端框架
- 实现 `index.html` SPA 结构：5 个标签页，导航栏
- 实现 `style.css`：完整 DESIGN.md 设计系统
- 实现 `app.js`：标签页切换、API 调用封装
- 前端启动时从 URL query 读取 token，后续 API 请求统一带 `X-ClipVault-Token`
- 手动验证：刷新浏览器后页面状态正常；无 token 的 API 写请求被拒绝

### Step 3: API 端点 + 视频处理页
- 实现 job manager：单任务运行、job 状态、events、result、error
- 实现 `POST /api/video`
- 实现 `GET /api/process/status?job_id=...`
- 实现 `GET /api/process/events?job_id=...` SSE 流式日志
- 视频处理 job 使用 CLI 子进程运行 `python -m clipvault video ...`
- stderr 逐行写入 events；stdout 最终 JSON 写入 result
- 实现视频处理页面 UI（URL 输入、选项、日志区、结果卡片）
- 测试：job 成功、job 失败、busy 返回 409、SSE 至少能推送 log/done

### Step 4: 仓库浏览页
- 实现 `GET /api/library`（扫描 + 读 index）
- 实现 `GET /api/library/transcript`
- 实现 `POST /api/open-path`，只允许打开 library root 内路径
- 实现侧边栏树 + 字幕预览 UI
- 测试：transcript 路径穿越被拒绝；合法 transcript 能读取；open-path 非 library 路径被拒绝

### Step 5: 创作者 + 队列 + 设置页
- 创作者管理 UI
- 队列状态/运行 UI；`POST /api/queue/run` 走 job manager + CLI 子进程
- 设置页 UI：保存 library/model/device/compute_type/cookies 路径到用户配置文件
- 测试：settings 读写；creator add/fetch/enqueue API；queue run busy/启动状态

### Step 6: 手动验收
- `python -m clipvault ui --no-open` 打印本地 URL 和 token
- 浏览器打开页面，5 个标签页可切换
- 无 token 的 `POST` 请求返回 401/403
- 视频页能启动一个真实短任务，实时看到日志，完成后显示 result
- 仓库页能读取 `_index.json` 并预览 `transcript.md`
- 打开输出目录只对 library 内路径生效
- 设置页保存后重启 server 仍能读取配置
- `.\clipvault.ps1 --help` 和现有 CLI 流程不受影响

## 相关文件参考

- `DESIGN.md` — 设计系统的完整规范（颜色、字体、间距、组件）
- `clipvault/cli.py` — 所有 CLI 子命令的定义和 `process_video` 签名
- `clipvault/library.py` — 仓库路径、manifest、索引
- `clipvault/creators.py` — 创作者注册、抓取、入队
- `clipvault/models.py` — 数据模型
- `AGENTS.md` — 项目总体说明和开发规则

`__main__.py` 入口参考（`from .cli import main; main()`），`ui` 子命令同理。
