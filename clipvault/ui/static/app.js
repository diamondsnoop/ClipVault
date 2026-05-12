const params = new URLSearchParams(window.location.search);
const TOKEN_STORAGE_KEY = "clipvault.ui.token";
const SIDEBAR_STORAGE_KEY = "clipvault.sidebarCollapsed";
const urlToken = params.get("token") || "";
if (urlToken) sessionStorage.setItem(TOKEN_STORAGE_KEY, urlToken);
const TOKEN = urlToken || sessionStorage.getItem(TOKEN_STORAGE_KEY) || "";

if (urlToken) {
  history.replaceState(null, "", window.location.pathname);
} else if (!TOKEN) {
  console.warn("ClipVault: no token in URL - API writes will fail");
}

const state = {
  intakeMode: "video",
  libraryMode: "subtitles",
  sidebarCollapsed: false,
  detailLogOpen: false,
  rawLog: [],
  logDir: "",
  settings: {},
  videos: [],
  collections: [],
  sources: [],
  search: "",
  libraryVisibleCount: 3,
};

const intakeConfigs = {
  video: {
    description: "粘贴单个视频链接，ClipVault 会优先获取平台字幕；没有字幕时再使用本地 ASR。",
    primaryLabel: "视频链接",
    primaryPlaceholder: "例如：https://www.bilibili.com/video/BV...",
    secondaryLabel: "保存到合集（可选）",
    secondaryPlaceholder: "例如：AI 工具观察",
    button: "开始获取字幕",
  },
  collection: {
    description: "合集清单解析正在接入。当前可先用视频模式逐条获取，并填写同一个合集名。",
    primaryLabel: "合集链接",
    primaryPlaceholder: "粘贴 Bilibili 合集 / YouTube 播放列表链接",
    secondaryLabel: "保存名称（可选）",
    secondaryPlaceholder: "例如：AI 课程合集",
    button: "查看当前用法",
  },
  source: {
    description: "保存为来源后，可以检查最近视频；批量勾选获取会在下一步接入。",
    primaryLabel: "来源链接",
    primaryPlaceholder: "粘贴 UP 主主页 / YouTube 频道链接",
    secondaryLabel: "来源名称（可选）",
    secondaryPlaceholder: "例如：跟李沐学 AI",
    button: "检查来源",
  },
};

const humanStepTemplates = [
  "获取视频信息",
  "查找平台字幕",
  "写入本地字幕",
  "建立本地索引",
  "出现在收藏夹",
];

let humanSteps = humanStepTemplates.map((label) => ({ label, state: "idle" }));

async function api(method, path, body) {
  const headers = { "Content-Type": "application/json" };
  if (TOKEN) headers["X-ClipVault-Token"] = TOKEN;
  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);
  const resp = await fetch("/api" + path, opts);
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(text || resp.statusText);
  }
  return resp.json();
}

function $(id) {
  return document.getElementById(id);
}

function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function displayValue(value, fallback) {
  const text = String(value || "").trim();
  if (!text || text === "untitled" || text === "unknown" || text === "unknown-uploader") return fallback;
  return text;
}

function displayTitle(value) {
  return displayValue(value, "未命名字幕");
}

function displayUploader(value) {
  return displayValue(value, "未知创作者");
}

function formatDate(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  if (/^\d{8}$/.test(text)) return `${text.slice(0, 4)}-${text.slice(4, 6)}-${text.slice(6, 8)}`;
  if (/^\d{4}-\d{2}-\d{2}/.test(text)) return text.slice(0, 10);
  return text.slice(0, 10);
}

function formatDuration(seconds) {
  const total = Number(seconds || 0);
  if (!Number.isFinite(total) || total <= 0) return "";
  const mins = Math.floor(total / 60);
  const secs = Math.floor(total % 60);
  return `${mins}:${String(secs).padStart(2, "0")}`;
}

function sourceLabel(source, fallback) {
  const raw = String(source || "").trim();
  if (fallback) return fallback;
  if (raw.startsWith("subtitle:")) return "平台字幕";
  if (raw.startsWith("automatic_caption:")) return "平台自动字幕";
  if (raw.startsWith("asr:")) return "本地 ASR";
  return raw || "字幕";
}

function normalizeSearchText(value) {
  return String(value || "").toLowerCase();
}

function parseLogLine(line) {
  const raw = String(line || "");
  const tags = [...raw.matchAll(/\[([^\]]+)\]/g)].map((match) => match[1]);
  const message = raw.replace(/^(\[[^\]]+\])+\s*/, "");
  let level = "info";
  if (tags.includes("错误")) level = "error";
  else if (tags.includes("警告")) level = "warning";
  else if (tags.includes("成功")) level = "success";
  const stage = tags.find((tag) => !["错误", "警告", "成功"].includes(tag)) || "";
  return { raw, tags, message, level, stage };
}

function parseDoneEvent(data) {
  try {
    const parsed = JSON.parse(data);
    if (parsed && typeof parsed === "object") return parsed;
  } catch (_) {}
  return { status: String(data || "") };
}

function resetWorkflowSteps(labels = humanStepTemplates) {
  humanSteps = labels.map((label) => ({ label, state: "idle" }));
}

function setWorkflowSteps(labels, currentIndex = 0) {
  resetWorkflowSteps(labels);
  if (Number.isInteger(currentIndex) && humanSteps[currentIndex]) {
    humanSteps[currentIndex].state = "current";
  }
  renderHumanStatus();
}

function setHumanSteps(index, status) {
  const labels = humanSteps.length ? humanSteps.map((step) => step.label) : humanStepTemplates;
  humanSteps = labels.map((label, i) => {
    if (i < index) return { label, state: "done" };
    if (i === index) return { label, state: status || "current" };
    return { label, state: "idle" };
  });
  renderHumanStatus();
}

function updateWorkflowStep(index, status) {
  if (!humanSteps[index]) return;
  humanSteps = humanSteps.map((step, i) => (
    i === index ? { ...step, state: status } : step
  ));
  renderHumanStatus();
}

function setAllStepsDone() {
  const labels = humanSteps.length ? humanSteps.map((step) => step.label) : humanStepTemplates;
  humanSteps = labels.map((label) => ({ label, state: "done" }));
  renderHumanStatus(100);
}

function resetHumanStatus() {
  state.rawLog = [];
  state.logDir = "";
  resetWorkflowSteps();
  renderHumanStatus(0);
  renderDetailLog();
}

function inferStepFromLog(line) {
  // This is a best-effort UX bridge for existing human-readable logs.
  // Raw logs remain the debug source of truth when wording changes.
  const text = String(line || "");
  if (/元数据|视频信息|识别平台|缓存/.test(text)) return 0;
  if (/字幕|平台字幕|ASR|音频/.test(text)) return 1;
  if (/导出|写入|transcript|Markdown|SRT|TXT/.test(text)) return 2;
  if (/索引|manifest|归档/.test(text)) return 3;
  if (/完成|成功/.test(text)) return 4;
  return -1;
}

function appendRuntimeLog(line) {
  const parsed = parseLogLine(line);
  state.rawLog.push(parsed);
  const step = inferStepFromLog(parsed.raw);
  if (parsed.level === "error") {
    const current = Math.max(step, humanSteps.findIndex((item) => item.state === "current"));
    setHumanSteps(current >= 0 ? current : 0, "error");
  } else if (step >= 0) {
    setHumanSteps(step, parsed.level === "success" ? "done" : "current");
  }
  renderDetailLog();
}

function progressFromSteps() {
  const done = humanSteps.filter((item) => item.state === "done").length;
  const current = humanSteps.some((item) => item.state === "current") ? 0.5 : 0;
  return Math.min(100, Math.round(((done + current) / humanSteps.length) * 100));
}

function renderHumanStatus(progressOverride) {
  const list = $("human-steps");
  const empty = $("human-status-empty");
  if (!list || !empty) return;
  const hasWork = humanSteps.some((item) => item.state !== "idle") || state.rawLog.length > 0;
  empty.style.display = hasWork ? "none" : "block";
  list.innerHTML = humanSteps.map((step) => (
    `<li class="human-step ${step.state}">
      <span class="step-dot"></span>
      <span>${escapeHtml(step.label)}</span>
    </li>`
  )).join("");
  const progress = typeof progressOverride === "number" ? progressOverride : progressFromSteps();
  if ($("progress-fill")) $("progress-fill").style.width = `${progress}%`;
  if ($("progress-label")) $("progress-label").textContent = `${progress}%`;
}

function renderDetailLog() {
  const log = $("detail-log");
  if (!log) return;
  if (!state.rawLog.length) {
    log.innerHTML = '<div class="log-line">详细日志会保留完整过程，方便后续 debug。</div>';
    return;
  }
  log.innerHTML = state.rawLog.map((entry) => (
    `<div class="log-line ${entry.level}">${escapeHtml(entry.raw)}</div>`
  )).join("");
  log.scrollTop = log.scrollHeight;
}

function renderLogActions() {
  const actions = $("detail-log-actions");
  if (!actions) return;
  actions.innerHTML = "";
  if (!state.logDir) return;
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "btn-secondary btn-small";
  btn.textContent = "打开日志文件夹";
  btn.addEventListener("click", () => openLocalPath(state.logDir));
  actions.appendChild(btn);
}

async function openLocalPath(path) {
  if (!path) return;
  await api("POST", "/open-path", { path });
}

function setSidebarCollapsed(collapsed, persist = false) {
  state.sidebarCollapsed = Boolean(collapsed);
  $("app-shell")?.classList.toggle("sidebar-collapsed", state.sidebarCollapsed);
  const icon = document.querySelector(".collapse-icon");
  if (icon) icon.textContent = state.sidebarCollapsed ? "»" : "«";
  if (persist) {
    try {
      localStorage.setItem(SIDEBAR_STORAGE_KEY, state.sidebarCollapsed ? "1" : "0");
    } catch (_) {}
  }
}

function bindNavigation() {
  document.querySelectorAll(".side-nav-item").forEach((button) => {
    button.addEventListener("click", () => {
      const tab = button.dataset.tab;
      document.querySelectorAll(".side-nav-item").forEach((item) => item.classList.toggle("active", item === button));
      document.querySelectorAll(".tab-pane").forEach((pane) => pane.classList.toggle("active", pane.id === `tab-${tab}`));
      if (tab === "settings") loadSettingsForm();
      if (tab === "home") loadHomeData();
    });
  });

  $("sidebar-toggle")?.addEventListener("click", () => {
    setSidebarCollapsed(!state.sidebarCollapsed, true);
  });
}

function bindIntake() {
  document.querySelectorAll("[data-intake-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      state.intakeMode = button.dataset.intakeMode || "video";
      document.querySelectorAll("[data-intake-mode]").forEach((item) => item.classList.toggle("active", item === button));
      renderIntakeMode();
    });
  });

  $("intake-collapse")?.addEventListener("click", () => {
    const body = $("intake-body");
    const collapsed = body?.classList.toggle("collapsed");
    $("intake-collapse").textContent = collapsed ? "展开获取区" : "收起获取区";
  });

  $("detail-log-toggle")?.addEventListener("click", () => {
    state.detailLogOpen = !state.detailLogOpen;
    $("detail-log-box")?.classList.toggle("collapsed", !state.detailLogOpen);
    $("detail-log-toggle").textContent = state.detailLogOpen ? "收起详细日志" : "查看详细日志";
  });

  $("intake-start")?.addEventListener("click", startIntake);
  renderIntakeMode();
  renderHumanStatus();
  renderDetailLog();
}

function renderIntakeMode() {
  const config = intakeConfigs[state.intakeMode] || intakeConfigs.video;
  if ($("intake-description")) $("intake-description").textContent = config.description;
  if ($("intake-primary-label")) $("intake-primary-label").textContent = config.primaryLabel;
  if ($("intake-primary")) $("intake-primary").placeholder = config.primaryPlaceholder;
  if ($("intake-secondary-label")) $("intake-secondary-label").textContent = config.secondaryLabel;
  if ($("intake-secondary")) $("intake-secondary").placeholder = config.secondaryPlaceholder;
  if ($("intake-start")) $("intake-start").textContent = config.button;
}

async function startIntake() {
  if (state.intakeMode === "video") {
    await startVideoJob();
  } else if (state.intakeMode === "source") {
    await checkSource();
  } else {
    previewCollection();
  }
}

async function startVideoJob() {
  const url = $("intake-primary")?.value.trim() || "";
  if (!url) {
    $("intake-primary")?.focus();
    return;
  }
  resetHumanStatus();
  setHumanSteps(0, "current");
  $("intake-start").disabled = true;
  $("intake-start").textContent = "正在获取...";

  try {
    const settings = state.settings || {};
    const resp = await api("POST", "/video", {
      url,
      series: $("intake-secondary")?.value.trim() || undefined,
      force: Boolean($("intake-force")?.checked),
      keep_audio: Boolean($("intake-keep-audio")?.checked),
      model: $("intake-model")?.value || settings.model || "small",
      device: $("intake-device")?.value || settings.device || "auto",
      compute_type: settings.compute_type || "auto",
      simplify_chinese: settings.simplify_chinese !== false,
    });
    if (resp.status !== "ok") throw new Error(resp.message || "启动任务失败");
    state.logDir = resp.log_dir || "";
    renderLogActions();
    const events = new EventSource(`/api/process/events?job_id=${encodeURIComponent(resp.job_id)}&token=${encodeURIComponent(TOKEN)}`);
    let lastError = "";
    events.addEventListener("log", (event) => appendRuntimeLog(event.data));
    events.addEventListener("result", () => {
      setHumanSteps(4, "current");
    });
    events.addEventListener("error", (event) => {
      lastError = String(event.data || "").trim();
      appendRuntimeLog(`[错误][流程] ${lastError}`);
    });
    events.addEventListener("done", async (event) => {
      const done = parseDoneEvent(event.data);
      events.close();
      $("intake-start").disabled = false;
      renderIntakeMode();
      if (done.log_dir) {
        state.logDir = done.log_dir;
        renderLogActions();
      }
      if (done.status === "succeeded") {
        setAllStepsDone();
        appendRuntimeLog("[成功][流程] 已完成，结果会出现在收藏夹");
        await loadHomeData();
      } else {
        const failure = done.error || lastError || "任务失败";
        appendRuntimeLog(`[错误][流程] ${failure}`);
        state.detailLogOpen = true;
        $("detail-log-box")?.classList.remove("collapsed");
        $("detail-log-toggle").textContent = "收起详细日志";
      }
    });
  } catch (err) {
    $("intake-start").disabled = false;
    renderIntakeMode();
    appendRuntimeLog(`[错误][流程] ${err.message}`);
  }
}

function previewCollection() {
  const url = $("intake-primary")?.value.trim() || "";
  resetHumanStatus();
  if (!url) {
    $("intake-primary")?.focus();
    return;
  }
  setWorkflowSteps(["读取合集链接", "说明当前可用方式", "等待合集清单解析接入"], 1);
  state.rawLog.push(parseLogLine("[信息][合集] 当前版本还不能直接解析合集清单。请先在“视频”模式逐个粘贴视频，并填写“保存到合集”；合集页会聚合这些已归档字幕。"));
  renderDetailLog();
}

async function checkSource() {
  const sourceUrl = $("intake-primary")?.value.trim() || "";
  const sourceName = $("intake-secondary")?.value.trim() || "";
  resetHumanStatus();
  if (!sourceUrl) {
    $("intake-primary")?.focus();
    return;
  }
  $("intake-start").disabled = true;
  $("intake-start").textContent = "正在检查...";
  setWorkflowSteps(["保存来源", "检查新视频", "标记已收藏内容", "等待批量获取接入"], 0);
  try {
    const added = await api("POST", "/creators/add", { source_url: sourceUrl, name: sourceName || undefined });
    updateWorkflowStep(0, "done");
    updateWorkflowStep(1, "current");
    const selector = added.creator?.id || sourceName || sourceUrl;
    const result = await api("POST", "/creators/fetch", { selector, limit: 10 });
    updateWorkflowStep(1, "done");
    updateWorkflowStep(2, "done");
    updateWorkflowStep(3, "current");
    appendRuntimeLog(`[成功][来源] 发现 ${result.new_count || 0} 个新视频，${result.processed_count || 0} 个已收藏。`);
    appendRuntimeLog("[信息][来源] 当前 Web UI 已完成来源登记和检查；批量勾选获取会在合集/来源资产化链路中接入。");
    await loadHomeData();
  } catch (err) {
    appendRuntimeLog(`[错误][来源] ${err.message}`);
  } finally {
    $("intake-start").disabled = false;
    renderIntakeMode();
    renderHumanStatus();
  }
}

function bindLibrary() {
  document.querySelectorAll("[data-library-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      state.libraryMode = button.dataset.libraryMode || "subtitles";
      state.libraryVisibleCount = 3;
      document.querySelectorAll("[data-library-mode]").forEach((item) => item.classList.toggle("active", item === button));
      renderLibraryList();
    });
  });
  $("library-search")?.addEventListener("input", (event) => {
    state.search = event.target.value || "";
    state.libraryVisibleCount = 3;
    renderLibraryList();
  });
}

async function loadHomeData() {
  await Promise.allSettled([loadLibrary(), loadSources()]);
  renderEnvStatus();
  renderLibraryList();
}

async function loadLibrary() {
  try {
    const data = await api("GET", "/library");
    const flattened = flattenLibrary(data.tree || []);
    state.videos = flattened.videos;
    state.collections = flattened.collections;
  } catch (_) {
    state.videos = [];
    state.collections = [];
  }
}

async function loadSources() {
  try {
    const data = await api("GET", "/creators");
    state.sources = data.creators || [];
  } catch (_) {
    state.sources = [];
  }
}

function flattenLibrary(tree) {
  const videos = [];
  const collections = [];
  for (const platform of tree || []) {
    for (const creator of platform.creators || []) {
      for (const video of creator.videos || []) {
        videos.push({ ...video, creator: creator.name, platform: platform.name });
      }
      for (const series of creator.series || []) {
        const seriesVideos = (series.videos || []).map((video) => ({
          ...video,
          creator: creator.name,
          platform: platform.name,
          series: series.name,
        }));
        videos.push(...seriesVideos);
        collections.push({
          name: series.name,
          creator: creator.name,
          platform: platform.name,
          video_count: seriesVideos.length,
          videos: seriesVideos,
          updated_at: latestDate(seriesVideos),
        });
      }
    }
  }
  videos.sort((a, b) => String(b.processed_at || "").localeCompare(String(a.processed_at || "")));
  collections.sort((a, b) => String(b.updated_at || "").localeCompare(String(a.updated_at || "")));
  return { videos, collections };
}

function latestDate(videos) {
  return (videos || []).map((item) => item.processed_at || item.upload_date || "").sort().pop() || "";
}

function renderEnvStatus() {
  const count = state.videos.filter((video) => video.has_transcript).length;
  const el = $("env-status");
  if (!el) return;
  el.innerHTML = `<span class="env-dot"></span><span>本地库已连接 · ${count} 个字幕</span>`;
}

function filterItems(items, fields) {
  const query = normalizeSearchText(state.search);
  if (!query) return items;
  return items.filter((item) => fields.some((field) => normalizeSearchText(item[field]).includes(query)));
}

function renderLibraryList() {
  const container = $("library-list");
  if (!container) return;
  if (state.libraryMode === "collections") {
    renderCollectionCards(container);
  } else if (state.libraryMode === "sources") {
    renderSourceCards(container);
  } else {
    renderSubtitleCards(container);
  }
}

function renderSubtitleCards(container) {
  const allVideos = filterItems(state.videos, ["title", "uploader", "creator", "platform", "subtitle_source_label"]);
  const videos = allVideos.slice(0, state.libraryVisibleCount);
  if (!allVideos.length) {
    container.innerHTML = '<div class="empty-card">还没有字幕。先在上方获取一条视频字幕。</div>';
    return;
  }
  container.innerHTML = videos.map((video, index) => {
    const title = displayTitle(video.title || video.name);
    const uploader = displayUploader(video.uploader || video.creator);
    const meta = [uploader, video.platform, sourceLabel(video.subtitle_source, video.subtitle_source_label), formatDuration(video.duration)]
      .filter(Boolean).join(" · ");
    return `<article class="subtitle-card" data-path="${escapeHtml(video.relative_path || "")}">
      <div class="thumb">${escapeHtml(formatDuration(video.duration) || "字幕")}</div>
      <div class="subtitle-main">
        <div class="subtitle-title">${escapeHtml(title)}</div>
        <div class="subtitle-meta">${escapeHtml(meta)}</div>
        <div class="subtitle-snippet" data-snippet-index="${index}">正在读取字幕片段...</div>
      </div>
      <div class="subtitle-side">
        <div class="subtitle-date">${escapeHtml(formatDate(video.processed_at || video.upload_date))}</div>
        <button class="text-button js-read-subtitle" data-index="${index}" type="button">查看字幕</button>
      </div>
    </article>`;
  }).join("");
  container.querySelectorAll(".js-read-subtitle").forEach((button) => {
    button.addEventListener("click", () => openTranscriptReader(videos[Number(button.dataset.index)]));
  });
  appendLoadMore(container, allVideos.length);
  hydrateSnippets(videos);
}

async function openTranscriptReader(video) {
  if (!video?.relative_path) return;
  const overlay = $("reader-overlay");
  const title = $("reader-title");
  const meta = $("reader-meta");
  const body = $("reader-content");
  const folderButton = $("reader-open-folder");
  if (!overlay || !title || !meta || !body) return;

  title.textContent = displayTitle(video.title || video.name);
  meta.textContent = [
    displayUploader(video.uploader || video.creator),
    video.platform,
    sourceLabel(video.subtitle_source, video.subtitle_source_label),
    formatDuration(video.duration),
  ].filter(Boolean).join(" · ");
  body.textContent = "正在读取字幕...";
  overlay.classList.remove("hidden");
  document.body.classList.add("reader-open");
  folderButton?.setAttribute("data-path", video.relative_path);

  try {
    const data = await api("GET", "/library/transcript?path=" + encodeURIComponent(video.relative_path));
    if (!data.has_transcript) {
      body.textContent = "这个条目还没有可读取的字幕文件。";
      return;
    }
    body.textContent = formatTranscriptForReading(data.content || "", data.format || "");
  } catch (err) {
    body.textContent = `读取字幕失败：${err.message}`;
  }
}

function formatTranscriptForReading(content, format) {
  let text = String(content || "");
  if (format === "srt" || format === "vtt") {
    text = text
      .replace(/^\d+\s*$/gm, "")
      .replace(/^\d{2}:\d{2}:\d{2}[,.]\d{3}\s+-->\s+\d{2}:\d{2}:\d{2}[,.]\d{3}.*$/gm, "")
      .replace(/^WEBVTT.*$/gm, "");
  }
  return text
    .replace(/```[\s\S]*?```/g, "")
    .replace(/^#+\s*/gm, "")
    .replace(/^-?\s*`?(\d{1,2}:\d{2}(?::\d{2})?)`?\s*/gm, "[$1] ")
    .replace(/\n{3,}/g, "\n\n")
    .trim() || "字幕文件为空。";
}

function closeTranscriptReader() {
  $("reader-overlay")?.classList.add("hidden");
  document.body.classList.remove("reader-open");
}

function bindTranscriptReader() {
  $("reader-close")?.addEventListener("click", closeTranscriptReader);
  $("reader-overlay")?.addEventListener("click", (event) => {
    if (event.target === $("reader-overlay")) closeTranscriptReader();
  });
  $("reader-open-folder")?.addEventListener("click", (event) => {
    const path = event.currentTarget.dataset.path;
    if (path) openLocalPath(path);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeTranscriptReader();
  });
}

function appendLoadMore(container, total) {
  if (total <= state.libraryVisibleCount) return;
  const rest = total - state.libraryVisibleCount;
  const wrap = document.createElement("div");
  wrap.className = "load-more-row";
  const button = document.createElement("button");
  button.className = "btn-secondary btn-small";
  button.type = "button";
  button.textContent = `加载更多（还有 ${rest} 条）`;
  button.addEventListener("click", () => {
    state.libraryVisibleCount += 6;
    renderLibraryList();
  });
  wrap.appendChild(button);
  container.appendChild(wrap);
}

async function hydrateSnippets(videos) {
  const targets = videos.slice(0, 12);
  for (let i = 0; i < targets.length; i += 1) {
    const video = targets[i];
    const el = document.querySelector(`[data-snippet-index="${i}"]`);
    if (!el || !video.relative_path) continue;
    try {
      const data = await api("GET", "/library/transcript?path=" + encodeURIComponent(video.relative_path));
      el.textContent = transcriptPreview(data.content || "") || "字幕已归档，打开后可查看全文。";
    } catch (_) {
      el.textContent = "字幕已归档，打开后可查看全文。";
    }
  }
}

function transcriptPreview(content) {
  return String(content || "")
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/#+\s*/g, "")
    .replace(/\[[0-9:.,\-\s>]+\]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 88);
}

function renderCollectionCards(container) {
  const allCollections = filterItems(state.collections, ["name", "creator", "platform"]);
  const collections = allCollections.slice(0, state.libraryVisibleCount);
  if (!allCollections.length) {
    container.innerHTML = '<div class="empty-card">还没有合集。你可以在获取字幕时填写“保存到合集”。</div>';
    return;
  }
  container.innerHTML = collections.map((item) => {
    const titles = (item.videos || []).slice(0, 4).map((video) => displayTitle(video.title)).join("、");
    return `<article class="collection-card">
      <div>
        <div class="subtitle-title">${escapeHtml(item.name)}</div>
        <div class="subtitle-meta">${item.video_count || 0} 个字幕 · 最近更新 ${escapeHtml(formatDate(item.updated_at) || "未知")}</div>
        <div class="subtitle-snippet">${escapeHtml(titles ? `包含：${titles}` : "这个合集已经创建，之后下载的字幕会自动归入这里。")}</div>
      </div>
      <button class="text-button js-filter-collection" data-name="${escapeHtml(item.name)}" type="button">打开合集</button>
    </article>`;
  }).join("");
  container.querySelectorAll(".js-filter-collection").forEach((button) => {
    button.addEventListener("click", () => {
      state.libraryMode = "subtitles";
      state.search = button.dataset.name || "";
      state.libraryVisibleCount = 3;
      $("library-search").value = state.search;
      document.querySelectorAll("[data-library-mode]").forEach((item) => {
        item.classList.toggle("active", item.dataset.libraryMode === "subtitles");
      });
      renderLibraryList();
    });
  });
  appendLoadMore(container, allCollections.length);
}

function renderSourceCards(container) {
  const allSources = filterItems(state.sources, ["name", "platform", "source_url"]);
  const sources = allSources.slice(0, state.libraryVisibleCount);
  if (!allSources.length) {
    container.innerHTML = '<div class="empty-card">还没有来源。你可以在上方“来源”模式里检查一个 UP 主或频道。</div>';
    return;
  }
  container.innerHTML = sources.map((source) => (
    `<article class="source-card">
      <div>
        <div class="subtitle-title">${escapeHtml(source.name || "未命名来源")}</div>
        <div class="subtitle-meta">${escapeHtml(source.platform || "")} · 最近检查 ${escapeHtml(formatDate(source.last_checked_at) || "尚未检查")}</div>
        <div class="subtitle-snippet">${escapeHtml(source.source_url || "")}</div>
      </div>
      <div class="source-actions">
        <button class="btn-secondary btn-small js-check-source" data-selector="${escapeHtml(source.id || source.name || "")}" type="button">检查更新</button>
        <button class="text-button js-view-source" data-name="${escapeHtml(source.name || "")}" type="button">查看字幕</button>
      </div>
    </article>`
  )).join("");
  container.querySelectorAll(".js-check-source").forEach((button) => {
    button.addEventListener("click", () => checkExistingSource(button.dataset.selector, button));
  });
  container.querySelectorAll(".js-view-source").forEach((button) => {
    button.addEventListener("click", () => {
      state.libraryMode = "subtitles";
      state.search = button.dataset.name || "";
      state.libraryVisibleCount = 3;
      $("library-search").value = state.search;
      document.querySelectorAll("[data-library-mode]").forEach((item) => {
        item.classList.toggle("active", item.dataset.libraryMode === "subtitles");
      });
      renderLibraryList();
    });
  });
  appendLoadMore(container, allSources.length);
}

async function checkExistingSource(selector, button) {
  if (!selector) return;
  const original = button.textContent;
  button.disabled = true;
  button.textContent = "检查中...";
  try {
    const result = await api("POST", "/creators/fetch", { selector, limit: 10 });
    button.textContent = `新视频 ${result.new_count || 0}`;
    await loadHomeData();
  } catch (err) {
    button.textContent = "检查失败";
  }
  setTimeout(() => {
    button.disabled = false;
    button.textContent = original;
  }, 1600);
}

async function loadStatus() {
  const env = $("env-status");
  try {
    await api("GET", "/status");
    env?.classList.remove("offline");
  } catch (_) {
    if (env) {
      env.classList.add("offline");
      env.innerHTML = '<span class="env-dot"></span><span>本地服务未连接</span>';
    }
  }
}

function bindSettings() {
  $("settings-save")?.addEventListener("click", saveSettings);
  $("settings-rebuild")?.addEventListener("click", async () => {
    const button = $("settings-rebuild");
    button.disabled = true;
    button.textContent = "重建中...";
    try {
      await api("POST", "/library/rebuild-index");
      await loadHomeData();
      button.textContent = "已重建";
    } catch (_) {
      button.textContent = "重建失败";
    }
    setTimeout(() => {
      button.disabled = false;
      button.textContent = "重建索引";
    }, 1500);
  });
}

async function loadSettingsForm() {
  try {
    const settings = await api("GET", "/settings");
    state.settings = settings;
    if ($("set-library")) $("set-library").value = settings.library || "";
    if ($("set-model")) $("set-model").value = settings.model || "small";
    if ($("set-device")) $("set-device").value = settings.device || "auto";
    if ($("set-compute-type")) $("set-compute-type").value = settings.compute_type || "auto";
    if ($("set-simplify-chinese")) $("set-simplify-chinese").checked = settings.simplify_chinese !== false;
    if ($("set-cookies")) $("set-cookies").value = settings.cookies || "";
    if ($("intake-model")) $("intake-model").value = settings.model || "small";
    if ($("intake-device")) $("intake-device").value = settings.device || "auto";
  } catch (_) {}
}

async function saveSettings() {
  const button = $("settings-save");
  button.disabled = true;
  button.textContent = "保存中...";
  try {
    await api("POST", "/settings", {
      library: $("set-library")?.value || "",
      model: $("set-model")?.value || "small",
      device: $("set-device")?.value || "auto",
      compute_type: $("set-compute-type")?.value || "auto",
      simplify_chinese: Boolean($("set-simplify-chinese")?.checked),
      cookies: $("set-cookies")?.value || null,
    });
    button.textContent = "已保存";
    await loadSettingsForm();
    await loadHomeData();
  } catch (_) {
    button.textContent = "保存失败";
  }
  setTimeout(() => {
    button.disabled = false;
    button.textContent = "保存设置";
  }, 1500);
}

function init() {
  try {
    setSidebarCollapsed(localStorage.getItem(SIDEBAR_STORAGE_KEY) === "1");
  } catch (_) {
    setSidebarCollapsed(false);
  }
  bindNavigation();
  bindIntake();
  bindLibrary();
  bindTranscriptReader();
  bindSettings();
  loadStatus();
  loadSettingsForm();
  loadHomeData();
}

init();
