// ── Token Management ───────────────────────────────────────────────

const params = new URLSearchParams(window.location.search);
const TOKEN_STORAGE_KEY = "clipvault.ui.token";
const urlToken = params.get("token") || "";
if (urlToken) {
  sessionStorage.setItem(TOKEN_STORAGE_KEY, urlToken);
}
const TOKEN = urlToken || sessionStorage.getItem(TOKEN_STORAGE_KEY) || "";

if (urlToken) {
  const clean = window.location.pathname;
  history.replaceState(null, "", clean);
} else if (!TOKEN) {
  console.warn("ClipVault: no token in URL — API writes will fail");
}

// ── API Helper ──────────────────────────────────────────────────────

async function api(method, path, body) {
  const headers = {
    "Content-Type": "application/json",
  };
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

// ── Tab Navigation ──────────────────────────────────────────────────

document.querySelectorAll(".nav-tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    const tab = btn.dataset.tab;
    document.querySelectorAll(".nav-tab").forEach((b) => b.classList.toggle("active", b === btn));
    document.querySelectorAll(".tab-pane").forEach((p) => p.classList.toggle("active", p.id === "tab-" + tab));
    if (typeof onTabSwitch === "function") onTabSwitch(tab);
  });
});

// ── Status ──────────────────────────────────────────────────────────

(async function checkStatus() {
  const el = document.getElementById("nav-status");
  try {
    const data = await api("GET", "/status");
    el.textContent = "v" + data.version;
    el.className = "nav-status connected";
  } catch (_) {
    el.textContent = "disconnected";
    el.className = "nav-status error";
  }
})();

// ── Video Processing ────────────────────────────────────────────────

const videoUrl = document.getElementById("video-url");
const videoSeries = document.getElementById("video-series");
const videoDevice = document.getElementById("video-device");
const videoModel = document.getElementById("video-model");
const videoForce = document.getElementById("video-force");
const videoKeepAudio = document.getElementById("video-keep-audio");
const videoStart = document.getElementById("video-start");
const videoLog = document.getElementById("video-log");
const videoLogArea = document.getElementById("video-log-area");
const videoResult = document.getElementById("video-result");
const videoResultCard = document.getElementById("video-result-card");

videoStart.addEventListener("click", startVideoJob);

async function startVideoJob() {
  const url = videoUrl.value.trim();
  if (!url) {
    videoUrl.focus();
    videoUrl.style.borderColor = "var(--color-error)";
    setTimeout(() => videoUrl.style.borderColor = "", 2000);
    return;
  }

  videoStart.disabled = true;
  videoStart.textContent = "处理中...";

  videoLog.textContent = "";
  videoLogArea.style.display = "block";
  videoResult.style.display = "none";

  let settings = {};
  try { settings = await api("GET", "/settings"); } catch (_) {
    appendLog("", "[settings] failed to read settings, using form/default values");
  }

  try {
    const body = {
      url,
      series: videoSeries.value.trim() || undefined,
      force: videoForce.checked,
      keep_audio: videoKeepAudio.checked,
      device: videoDevice.value || settings.device || "auto",
      model: videoModel.value || settings.model || "small",
    };

    const resp = await api("POST", "/video", body);
    if (resp.status !== "ok") {
      appendLog("error", "[error] " + (resp.message || "Failed to start job"));
      videoStart.disabled = false;
      videoStart.textContent = "开始处理";
      return;
    }

    const jobId = resp.job_id;
    const events = new EventSource("/api/process/events?job_id=" + jobId + "&token=" + TOKEN);
    let resultShown = false;

    events.addEventListener("log", (e) => {
      const line = e.data;
      if (line.startsWith("[error]")) {
        appendLog("error", line);
      } else if (line.includes("status=ok") || line.includes("status=cached")) {
        appendLog("success", line);
      } else {
        appendLog("", line);
      }
    });

    events.addEventListener("result", (e) => {
      if (!resultShown) {
        resultShown = true;
        showResult(JSON.parse(e.data));
      }
    });

    events.addEventListener("error", (e) => {
      appendLog("error", "[error] " + e.data);
    });

    events.addEventListener("done", () => {
      events.close();
      videoStart.disabled = false;
      videoStart.textContent = "开始处理";
      appendLog("", "[done] 处理完成");
    });

  } catch (err) {
    appendLog("error", "[error] " + err.message);
    videoStart.disabled = false;
    videoStart.textContent = "开始处理";
  }
}

function appendLog(cls, text) {
  const line = document.createElement("div");
  line.className = "log-line" + (cls ? " " + cls : "");
  line.textContent = text;
  videoLog.appendChild(line);
  videoLog.scrollTop = videoLog.scrollHeight;
}

function showResult(data) {
  const folder = data.folder || "";
  const platform = data.platform || "";
  const series = data.series || "";
  const source = data.source || "";
  const segments = data.segments ?? "";

  let html = '<div class="flex-col-md">';

  html += '<div><span class="badge ' + (data.status === "ok" ? "badge-success" : "") + '">' + escapeHtml(data.status) + '</span></div>';

  html += '<table style="width: 100%; border-collapse: collapse;">';
  const rows = [
    ["标题", data.title],
    ["创作者", data.uploader],
    ["视频 ID", data.video_id],
    ["平台", platform],
    ["系列", series],
    ["字幕来源", source],
    ["片段数", segments],
  ];
  for (const [label, val] of rows) {
    if (val) {
      html += '<tr><td style="padding: 4px 12px 4px 0; color: var(--color-muted); white-space: nowrap;">' + escapeHtml(label) + '</td>'
            + '<td style="padding: 4px 0;">' + escapeHtml(String(val)) + '</td></tr>';
    }
  }
  html += '</table>';

  html += '<div class="flex-row" style="margin-top: 8px;">';
  if (folder) {
    html += '<button class="btn-secondary btn-small js-open-folder" data-path="' + escapeHtml(folder) + '">打开文件夹</button>';
  }
  html += '</div>';
  html += '</div>';

  videoResultCard.innerHTML = html;
  videoResult.style.display = "block";

  videoResultCard.querySelector(".js-open-folder")?.addEventListener("click", (e) => {
    const path = e.currentTarget.dataset.path;
    api("POST", "/open-path", { path }).catch(err => appendLog("error", "[error] " + err.message));
  });
}

// ── Library ──────────────────────────────────────────────────────

const libraryTreeEl = document.getElementById("library-tree");
const libraryDetailEl = document.getElementById("library-detail");

document.getElementById("library-rebuild")?.addEventListener("click", async function () {
  this.disabled = true;
  this.textContent = "重建中...";
  try {
    const result = await api("POST", "/library/rebuild-index");
    if (result.status === "ok") await loadLibraryTree();
  } catch (err) {
    libraryTreeEl.innerHTML = '<p style="color: var(--color-error);">' + escapeHtml(err.message) + "</p>";
  }
  this.disabled = false;
  this.textContent = "重建索引";
});

async function loadLibraryTree() {
  libraryTreeEl.innerHTML = '<p class="muted">加载中...</p>';
  try {
    const data = await api("GET", "/library");
    renderLibraryTree(data.tree || []);
  } catch (err) {
    libraryTreeEl.innerHTML = '<p class="muted">加载失败: ' + escapeHtml(err.message) + "</p>";
  }
}

function renderLibraryTree(tree) {
  if (!tree || tree.length === 0) {
    libraryTreeEl.innerHTML = '<p class="muted">仓库为空</p>';
    return;
  }

  const root = document.createElement("ul");
  root.className = "tree";

  for (const platform of tree) {
    const li = buildTreeBranch(platform.name, "platform",
      (platform.creators || []).map(c => {
        const kids = [];
        for (const s of c.series || []) {
          const seriesVideos = (s.videos || []).map(v => buildVideoNode(v));
          kids.push(createTreeNode(s.name, ["series"], seriesVideos));
        }
        for (const v of c.videos || []) {
          kids.push(buildVideoNode(v));
        }
        return createTreeNode(c.name, ["creator"], kids);
      })
    );
    root.appendChild(li);
  }

  libraryTreeEl.innerHTML = "";
  libraryTreeEl.appendChild(root);
}

function buildVideoNode(v) {
  const source = String(v.subtitle_source || "");
  const dotClass = source.startsWith("asr:") ? "warning" : v.has_transcript ? "success" : "";
  const label = document.createElement("span");
  if (dotClass) {
    label.innerHTML = '<span class="status-dot ' + dotClass + '"></span> ' + escapeHtml(v.title || v.name);
  } else {
    label.textContent = v.title || v.name;
  }
  return createLeafNode(label, ["video"], () => selectVideo(v));
}

function createTreeNode(labelText, classes = [], children = []) {
  const li = document.createElement("li");
  li.className = "tree-node";

  const label = document.createElement("div");
  label.className = "label" + (classes.length ? " " + classes.join(" ") : "");

  if (children.length) {
    label.innerHTML = '<span class="toggle">▶</span> ' + escapeHtml(labelText);
    label.addEventListener("click", function () {
      const ch = this.parentElement.querySelector(".tree-children");
      if (ch) {
        ch.classList.toggle("open");
        this.querySelector(".toggle").textContent = ch.classList.contains("open") ? "▼" : "▶";
      }
    });
    li.appendChild(label);

    const ul = document.createElement("ul");
    ul.className = "tree-children";
    children.forEach(c => ul.appendChild(c));
    li.appendChild(ul);
  } else {
    label.textContent = labelText;
    li.appendChild(label);
  }

  return li;
}

function createLeafNode(contentEl, classes, onClick) {
  const li = document.createElement("li");
  li.className = "tree-node";
  const label = document.createElement("div");
  label.className = "label" + (classes.length ? " " + classes.join(" ") : "");
  label.appendChild(contentEl);
  label.addEventListener("click", function (e) {
    e.stopPropagation();
    libraryTreeEl.querySelectorAll(".label.selected").forEach(el => el.classList.remove("selected"));
    this.classList.add("selected");
    onClick();
  });
  li.appendChild(label);
  return li;
}

function buildTreeBranch(labelText, cls, children = []) {
  const li = document.createElement("li");
  li.className = "tree-node";
  const label = document.createElement("div");
  label.className = "label" + (cls ? " " + cls : "");
  label.innerHTML = '<span class="toggle">▶</span> ' + escapeHtml(labelText);
  label.addEventListener("click", function () {
    const ch = this.parentElement.querySelector(".tree-children");
    if (ch) {
      ch.classList.toggle("open");
      this.querySelector(".toggle").textContent = ch.classList.contains("open") ? "▼" : "▶";
    }
  });
  li.appendChild(label);

  const ul = document.createElement("ul");
  ul.className = "tree-children";
  children.forEach(c => ul.appendChild(c));
  li.appendChild(ul);
  return li;
}

async function selectVideo(video) {
  libraryDetailEl.innerHTML = '<div class="card"><p class="muted">加载中...</p></div>';

  try {
    const [manifest, transcript] = await Promise.all([
      api("GET", "/library/video?path=" + encodeURIComponent(video.relative_path)),
      api("GET", "/library/transcript?path=" + encodeURIComponent(video.relative_path)),
    ]);

    let html = '<div class="card"><div class="flex-col-md">';
    html += "<h2>" + escapeHtml(manifest.title || video.name) + "</h2>";
    html += '<table style="width: 100%; border-collapse: collapse;">';
    const rows = [
      ["视频 ID", manifest.video_id],
      ["平台", manifest.platform],
      ["创作者", manifest.uploader],
      ["系列", manifest.series],
      ["字幕来源", manifest.subtitle_source],
      ["时长", manifest.duration ? Math.floor(manifest.duration / 60) + "m" : ""],
      ["上传日期", manifest.upload_date],
      ["处理时间", manifest.processed_at],
    ];
    for (const [label, val] of rows) {
      if (val) {
        html += '<tr><td style="padding: 4px 12px 4px 0; color: var(--color-muted); white-space: nowrap;">' + escapeHtml(label) + "</td>"
              + "<td style=\"padding: 4px 0;\">" + escapeHtml(String(val)) + "</td></tr>";
      }
    }
    html += "</table>";
    html += '<div class="flex-row" style="margin-top: 8px;">'
          + '<button class="btn-secondary btn-small js-open-folder" data-path="' + escapeHtml(video.relative_path) + '">打开文件夹</button>'
          + "</div>";
    html += "</div></div>";

    if (transcript.has_transcript) {
      html += '<h2 class="mt-lg mb-md">字幕 (' + escapeHtml(transcript.format) + ")</h2>";
      html += '<div class="log-console" style="max-height: 500px;">' + escapeHtml(transcript.content) + "</div>";
    }

    libraryDetailEl.innerHTML = html;
    libraryDetailEl.querySelector(".js-open-folder")?.addEventListener("click", function () {
      api("POST", "/open-path", { path: video.relative_path }).catch(err => {
        libraryDetailEl.innerHTML = '<div class="card"><p style="color: var(--color-error);">' + escapeHtml(err.message) + "</p></div>";
      });
    });

  } catch (err) {
    libraryDetailEl.innerHTML = '<div class="card"><p style="color: var(--color-error);">' + escapeHtml(err.message) + "</p></div>";
  }
}

// ── Creators ────────────────────────────────────────────────────

const creatorUrl = document.getElementById("creator-url");
const creatorName = document.getElementById("creator-name");
const creatorAdd = document.getElementById("creator-add");
const creatorList = document.getElementById("creator-list");

creatorAdd?.addEventListener("click", addCreator);

async function loadCreators() {
  creatorList.innerHTML = '<p class="muted">加载中...</p>';
  try {
    const data = await api("GET", "/creators");
    renderCreators(data.creators || []);
  } catch (err) {
    creatorList.innerHTML = '<p class="muted">加载失败: ' + escapeHtml(err.message) + "</p>";
  }
}

function renderCreators(creators) {
  if (!creators || creators.length === 0) {
    creatorList.innerHTML = '<p class="muted">还没有添加任何创作者</p>';
    return;
  }

  let html = "";
  for (const c of creators) {
    html += '<div class="card" style="padding: var(--spacing-md);">'
          + '<div class="flex-row" style="justify-content: space-between;">'
          +   "<div>"
          +     "<strong>" + escapeHtml(c.name || "") + "</strong>"
          +     ' <span class="badge" style="margin-left: 8px;">' + escapeHtml(c.platform || "") + "</span>"
          +     '<p class="small muted">' + escapeHtml(c.source_url || "") + "</p>"
          +   "</div>"
          +   '<div class="flex-row">'
          +     '<button class="btn-secondary btn-small js-fetch" data-selector="' + escapeHtml(c.id || c.name || "") + '" data-name="' + escapeHtml(c.name || "") + '">预览</button>'
          +     '<button class="btn-secondary btn-small js-enqueue" data-selector="' + escapeHtml(c.id || c.name || "") + '">加入队列</button>'
          +   "</div>"
          + "</div>"
          + '<div class="js-fetch-result" style="display: none; margin-top: var(--spacing-sm);"></div>'
          + "</div>";
  }
  creatorList.innerHTML = html;

  creatorList.querySelectorAll(".js-fetch").forEach(btn => {
    btn.addEventListener("click", function () { fetchCreator(this.dataset.selector, this); });
  });
  creatorList.querySelectorAll(".js-enqueue").forEach(btn => {
    btn.addEventListener("click", function () { enqueueCreator(this.dataset.selector, this); });
  });
}

async function addCreator() {
  const url = creatorUrl.value.trim();
  if (!url) { creatorUrl.focus(); return; }

  creatorAdd.disabled = true;
  creatorAdd.textContent = "添加中...";
  try {
    await api("POST", "/creators/add", {
      source_url: url,
      name: creatorName.value.trim() || undefined,
    });
    creatorUrl.value = "";
    creatorName.value = "";
    await loadCreators();
  } catch (err) {
    creatorList.innerHTML = '<p style="color: var(--color-error);">添加失败: ' + escapeHtml(err.message) + "</p>";
  }
  creatorAdd.disabled = false;
  creatorAdd.textContent = "添加";
}

async function fetchCreator(selector, btn) {
  const card = btn.closest(".card");
  const resultEl = card.querySelector(".js-fetch-result");
  resultEl.style.display = "block";
  resultEl.innerHTML = '<p class="muted">加载中...</p>';
  btn.disabled = true;

  try {
    const data = await api("POST", "/creators/fetch", { selector, limit: 10 });
    let html = '<p class="small muted">新视频: ' + (data.new_count || 0) + ", 已处理: " + (data.processed_count || 0) + "</p>";
    if (data.entries && data.entries.length) {
      html += '<div style="max-height: 300px; overflow-y: auto; margin-top: var(--spacing-xs);">';
      for (const entry of data.entries) {
        const dotClass = entry.library_status === "processed" ? "success" : "";
        html += '<div class="flex-row" style="padding: 2px 0; font-size: 13px;">'
              + '<span class="status-dot ' + dotClass + '" style="margin-right: 8px;"></span>'
              + "<span>" + escapeHtml(entry.title || "untitled") + "</span>"
              + ' <span class="muted small">' + (entry.library_status === "processed" ? "已处理" : "新") + "</span>"
              + "</div>";
      }
      html += "</div>";
    }
    resultEl.innerHTML = html;
  } catch (err) {
    resultEl.innerHTML = '<p style="color: var(--color-error);">' + escapeHtml(err.message) + "</p>";
  }
  btn.disabled = false;
}

async function enqueueCreator(selector, btn) {
  btn.disabled = true;
  btn.textContent = "加入中...";
  try {
    const data = await api("POST", "/creators/enqueue", { selector, limit: 10 });
    btn.textContent = "已加入 ✓";
    setTimeout(() => { btn.textContent = "加入队列"; btn.disabled = false; }, 2000);
  } catch (err) {
    btn.textContent = "加入队列";
    btn.disabled = false;
    creatorList.innerHTML = '<p style="color: var(--color-error);">加入队列失败: ' + escapeHtml(err.message) + "</p>";
  }
}

// ── Queue ────────────────────────────────────────────────────────

const queueStatusEl = document.getElementById("queue-status");
const queueListEl = document.getElementById("queue-list");
const queueRunBtn = document.getElementById("queue-run");
const queueRunLimit = document.getElementById("queue-run-limit");
const queueRetryFailed = document.getElementById("queue-retry-failed");
const queueKeepAudio = document.getElementById("queue-keep-audio");
const queueVerbose = document.getElementById("queue-verbose");
const queueLogArea = document.getElementById("queue-log-area");
const queueLog = document.getElementById("queue-log");

let _queueFilter = "all";
let _queueData = { jobs: [] };

queueRunBtn?.addEventListener("click", startQueueRun);

async function loadQueue() {
  queueStatusEl.innerHTML = '<p class="muted">加载中...</p>';
  queueListEl.innerHTML = "";
  try {
    const data = await api("GET", "/queue");
    _queueData = data;
    renderQueueStatus(data);
    renderQueueJobs(data);
  } catch (err) {
    queueStatusEl.innerHTML = '<p class="muted">加载失败: ' + escapeHtml(err.message) + "</p>";
  }
}

function renderQueueStatus(data) {
  const counts = data.counts || {};
  const total = data.total || 0;
  const pending = counts.pending || 0;
  const done = counts.done || 0;
  const running = counts.running || 0;
  const failed = counts.failed || 0;

  queueStatusEl.innerHTML = '<div class="flex-row" style="flex-wrap: wrap; gap: var(--spacing-lg);">'
    + '<div><span class="badge">总计</span> ' + total + "</div>"
    + '<div><span class="badge badge-warning">等待中</span> ' + pending + "</div>"
    + '<div><span class="badge" style="background: var(--color-accent-teal); color: #fff;">运行中</span> ' + running + "</div>"
    + '<div><span class="badge badge-success">完成</span> ' + done + "</div>"
    + '<div><span class="badge badge-error">失败</span> ' + failed + "</div>"
    + "</div>";
}

function renderQueueJobs(data) {
  const jobs = data.jobs || [];
  let filtered = jobs;
  if (_queueFilter !== "all") {
    filtered = jobs.filter(j => j.status === _queueFilter);
  }

  if (filtered.length === 0 && _queueFilter === "all") {
    queueListEl.innerHTML = '<p class="muted mt-md">队列为空</p>';
    return;
  }

  let html = '<div class="flex-row mt-md mb-md">'
    + '<button class="btn-secondary btn-small js-qfilter' + (_queueFilter === "all" ? " active" : "") + '" data-filter="all">全部 (' + jobs.length + ")</button>"
    + '<button class="btn-secondary btn-small js-qfilter' + (_queueFilter === "pending" ? " active" : "") + '" data-filter="pending">等待中</button>'
    + '<button class="btn-secondary btn-small js-qfilter' + (_queueFilter === "done" ? " active" : "") + '" data-filter="done">完成</button>'
    + '<button class="btn-secondary btn-small js-qfilter' + (_queueFilter === "failed" ? " active" : "") + '" data-filter="failed">失败</button>'
    + "</div>";

  if (filtered.length === 0) {
    html += '<p class="muted">没有符合条件的任务</p>';
    queueListEl.innerHTML = html;
    bindQueueFilters();
    return;
  }

  html += '<div style="display: flex; flex-direction: column; gap: var(--spacing-sm);">';
  for (const job of filtered) {
    const statusColor = job.status === "done" ? "success"
      : job.status === "failed" ? "error"
      : job.status === "running" ? "warning" : "";
    html += '<div class="card" style="padding: var(--spacing-md); display: flex; justify-content: space-between; align-items: center;">'
      +   "<div>"
      +     '<span class="status-dot ' + statusColor + '" style="margin-right: 8px;"></span>'
      +     "<strong>" + escapeHtml(job.title || "untitled") + "</strong>"
      +     ' <span class="small muted">' + escapeHtml(job.platform || "") + "</span>"
      +     '<p class="small muted">' + escapeHtml(job.source_url || "") + "</p>"
      +   "</div>"
      +   '<div class="flex-row">'
      +     (job.status === "pending"
        ? '<button class="btn-secondary btn-small js-qremove" data-job-id="' + escapeHtml(job.id) + '">移除</button>'
        : "")
      +   "</div>"
      + "</div>";
  }
  html += "</div>";

  queueListEl.innerHTML = html;
  bindQueueFilters();
  bindQueueRemove();
}

function bindQueueFilters() {
  queueListEl.querySelectorAll(".js-qfilter").forEach(btn => {
    btn.addEventListener("click", function () {
      queueListEl.querySelectorAll(".js-qfilter").forEach(b => b.classList.remove("active"));
      this.classList.add("active");
      _queueFilter = this.dataset.filter || "all";
      renderQueueJobs(_queueData);
    });
  });
}

function bindQueueRemove() {
  queueListEl.querySelectorAll(".js-qremove").forEach(btn => {
    btn.addEventListener("click", async function () {
      try {
        await api("POST", "/queue/remove", { job_id: this.dataset.jobId });
        await loadQueue();
      } catch (err) {
        queueListEl.innerHTML = '<p style="color: var(--color-error);">移除失败: ' + escapeHtml(err.message) + "</p>";
      }
    });
  });
}

async function startQueueRun() {
  queueRunBtn.disabled = true;
  queueRunBtn.textContent = "运行中...";
  queueLog.textContent = "";
  queueLogArea.style.display = "block";

  try {
    const limit = Math.max(1, parseInt(queueRunLimit.value || "1", 10));
    const resp = await api("POST", "/queue/run", {
      limit,
      retry_failed: queueRetryFailed.checked,
      keep_audio: queueKeepAudio.checked,
      verbose: queueVerbose.checked,
    });
    if (resp.status !== "ok") {
      appendQueueLog("error", "[error] " + (resp.message || "Failed to start queue run"));
      queueRunBtn.disabled = false;
      queueRunBtn.textContent = "运行队列";
      return;
    }

    const events = new EventSource("/api/process/events?job_id=" + encodeURIComponent(resp.job_id) + "&token=" + encodeURIComponent(TOKEN));

    events.addEventListener("log", (e) => {
      const line = e.data;
      appendQueueLog(line.startsWith("[error]") ? "error" : "", line);
    });
    events.addEventListener("error", (e) => {
      appendQueueLog("error", "[error] " + e.data);
    });
    events.addEventListener("done", async () => {
      events.close();
      queueRunBtn.disabled = false;
      queueRunBtn.textContent = "运行队列";
      appendQueueLog("", "[done] 队列运行结束");
      await loadQueue();
    });
  } catch (err) {
    appendQueueLog("error", "[error] " + err.message);
    queueRunBtn.disabled = false;
    queueRunBtn.textContent = "运行队列";
  }
}

function appendQueueLog(cls, text) {
  const line = document.createElement("div");
  line.className = "log-line" + (cls ? " " + cls : "");
  line.textContent = text;
  queueLog.appendChild(line);
  queueLog.scrollTop = queueLog.scrollHeight;
}

// ── Settings ──────────────────────────────────────────────────────

const setLibrary = document.getElementById("set-library");
const setModel = document.getElementById("set-model");
const setDevice = document.getElementById("set-device");
const setCookies = document.getElementById("set-cookies");
const setSave = document.getElementById("settings-save");

setSave?.addEventListener("click", saveSettings);

async function loadSettingsForm() {
  try {
    const s = await api("GET", "/settings");
    if (setLibrary) setLibrary.value = s.library || "";
    if (setModel) setModel.value = s.model || "small";
    if (setDevice) setDevice.value = s.device || "auto";
    if (setCookies) setCookies.value = s.cookies || "";
  } catch (_) {}
}

async function saveSettings() {
  setSave.disabled = true;
  setSave.textContent = "保存中...";
  try {
    const payload = {
      library: setLibrary.value,
      model: setModel.value,
      device: setDevice.value,
      cookies: setCookies.value || null,
    };
    await api("POST", "/settings", payload);
    setSave.textContent = "已保存";
    await loadSettingsForm();
    if (document.getElementById("tab-library")?.classList.contains("active")) {
      await loadLibraryTree();
    }
    setTimeout(() => { setSave.textContent = "保存设置"; setSave.disabled = false; }, 1500);
  } catch (err) {
    setSave.textContent = "保存失败";
    setTimeout(() => { setSave.textContent = "保存设置"; setSave.disabled = false; }, 2000);
  }
}

// ── Utilities ─────────────────────────────────────────────────────

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// ── Tab Switch Handler ────────────────────────────────────────────

function onTabSwitch(tab) {
  switch (tab) {
    case "library":
      loadLibraryTree();
      break;
    case "creators":
      loadCreators();
      break;
    case "queue":
      loadQueue();
      break;
    case "settings":
      loadSettingsForm();
      break;
  }
}
