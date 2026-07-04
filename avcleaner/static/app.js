const state = {
  settings: null,
  scan: null,
  plan: null,
};

const $ = (selector) => document.querySelector(selector);

function toast(message) {
  const node = $("#toast");
  node.textContent = message;
  node.classList.add("show");
  window.setTimeout(() => node.classList.remove("show"), 2600);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "操作失败");
  }
  return response.json();
}

function setMetrics() {
  const items = state.plan?.items || [];
  $("#metricFiles").textContent = state.scan?.total_files || 0;
  $("#metricRename").textContent = items.filter((item) => item.action === "rename").length;
  $("#metricReview").textContent = items.filter((item) => item.action === "review").length;
  $("#metricTrash").textContent = items.filter((item) => item.action === "quarantine").length;
}

function renderPlan() {
  const body = $("#planBody");
  body.innerHTML = "";
  const items = state.plan?.items || [];
  for (const item of items) {
    const row = document.createElement("tr");
    row.dataset.id = item.id;

    const checked = document.createElement("input");
    checked.type = "checkbox";
    checked.checked = item.checked;
    checked.disabled = item.action === "keep" || item.action === "review";
    checked.addEventListener("change", () => {
      item.checked = checked.checked;
    });

    const nameInput = document.createElement("input");
    nameInput.className = "name-input";
    nameInput.value = item.suggested_name;
    nameInput.disabled = item.action !== "rename";
    nameInput.addEventListener("input", () => {
      item.suggested_name = nameInput.value;
      item.source = "manual";
      const slash = item.target_path.lastIndexOf("\\");
      const altSlash = item.target_path.lastIndexOf("/");
      const index = Math.max(slash, altSlash);
      const dir = index >= 0 ? item.target_path.slice(0, index + 1) : "";
      item.target_path = dir + item.suggested_name;
    });

    row.append(
      cell(checked),
      cell(pill(item.action)),
      cellText(item.original_name),
      cell(nameInput),
      cellText(item.confidence.toFixed(2)),
      cellText(item.reason),
      cellWarnings(item.warnings)
    );
    body.append(row);
  }
  renderTrash();
  setMetrics();
}

function renderTrash() {
  const body = $("#trashBody");
  body.innerHTML = "";
  for (const item of (state.plan?.items || []).filter((row) => row.action === "quarantine")) {
    const row = document.createElement("tr");
    row.append(cellText(item.original_name), cellText(item.relative_path), cellText(item.reason), cellText(formatSize(item.size)));
    body.append(row);
  }
}

function cell(node) {
  const td = document.createElement("td");
  td.append(node);
  return td;
}

function cellText(text) {
  const td = document.createElement("td");
  td.textContent = text || "";
  return td;
}

function cellWarnings(warnings) {
  const td = document.createElement("td");
  td.className = warnings?.some((warning) => warning.includes("目标") || warning.includes("非法")) ? "error" : "warning";
  td.textContent = (warnings || []).join("；");
  return td;
}

function pill(action) {
  const span = document.createElement("span");
  span.className = `pill ${action}`;
  span.textContent = action;
  return span;
}

function formatSize(bytes) {
  if (!bytes) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

async function loadSettings() {
  state.settings = await api("/api/settings");
  $("#llmProvider").value = state.settings.llm.provider;
  $("#llmBaseUrl").value = state.settings.llm.base_url;
  $("#llmModel").value = state.settings.llm.model;
  $("#llmApiKey").value = state.settings.llm.api_key;
  $("#llmSendPath").checked = state.settings.llm.send_full_path;
}

async function saveSettings() {
  state.settings.llm.provider = $("#llmProvider").value;
  state.settings.llm.base_url = $("#llmBaseUrl").value;
  state.settings.llm.model = $("#llmModel").value;
  state.settings.llm.api_key = $("#llmApiKey").value;
  state.settings.llm.send_full_path = $("#llmSendPath").checked;
  state.settings = await api("/api/settings", {
    method: "PUT",
    body: JSON.stringify(state.settings),
  });
  toast("设置已保存");
}

async function scan() {
  const root = $("#rootPath").value.trim();
  if (!root) {
    toast("请输入目录");
    return;
  }
  state.scan = await api("/api/scan", {
    method: "POST",
    body: JSON.stringify({ root_path: root, recursive: true }),
  });
  state.plan = null;
  renderPlan();
  toast(`扫描完成：${state.scan.total_files} 个文件`);
}

async function plan() {
  if (!state.scan) {
    await scan();
  }
  state.plan = await api("/api/plan", {
    method: "POST",
    body: JSON.stringify({
      root_path: state.scan.root_path,
      files: state.scan.files,
      rules: state.settings.rules,
    }),
  });
  renderPlan();
  toast("预览已生成");
}

async function llmSuggest() {
  if (!state.plan) {
    await plan();
  }
  const reviewItems = state.plan.items.filter((item) => item.action === "review" || (item.checked && item.confidence < 0.85));
  if (!reviewItems.length) {
    toast("没有需要 LLM 处理的项目");
    return;
  }
  const names = state.scan.files.map((file) => file.name);
  const response = await api("/api/llm/suggest", {
    method: "POST",
    body: JSON.stringify({
      items: reviewItems.map((item) => ({
        id: item.id,
        name: item.original_name,
        extension: item.extension,
        adjacent_names: names.filter((name) => name !== item.original_name).slice(0, 8),
      })),
    }),
  });
  for (const suggestion of response.suggestions) {
    const item = state.plan.items.find((row) => row.id === suggestion.item_id);
    if (!item) continue;
    item.suggested_name = suggestion.suggested_name;
    item.media_code = suggestion.media_code;
    item.part_suffix = suggestion.part_suffix;
    item.variant = suggestion.variant;
    item.removed_tokens = suggestion.removed_tokens;
    item.confidence = suggestion.confidence;
    item.reason = suggestion.reason;
    item.warnings = suggestion.warnings;
    item.source = "llm";
    item.action = suggestion.confidence >= 0.7 ? "rename" : "review";
    item.checked = suggestion.confidence >= 0.85;
    const slash = item.source_path.lastIndexOf("\\");
    const altSlash = item.source_path.lastIndexOf("/");
    const index = Math.max(slash, altSlash);
    const dir = index >= 0 ? item.source_path.slice(0, index + 1) : "";
    item.target_path = dir + item.suggested_name;
  }
  renderPlan();
  toast("LLM 建议已返回");
}

async function executeSelected() {
  if (!state.plan) {
    toast("没有预览计划");
    return;
  }
  const selected = state.plan.items.filter((item) => item.checked && ["rename", "quarantine"].includes(item.action));
  if (!selected.length) {
    toast("没有选中项");
    return;
  }
  const response = await api("/api/execute", {
    method: "POST",
    body: JSON.stringify({ root_path: state.plan.root_path, items: selected, confirm: true }),
  });
  toast(`执行完成：${response.run_id}`);
  await refreshRuns();
  await scan();
  await plan();
}

async function refreshRuns() {
  const runs = await api("/api/runs");
  const body = $("#runsBody");
  body.innerHTML = "";
  for (const run of runs) {
    const button = document.createElement("button");
    button.textContent = "回滚";
    button.addEventListener("click", async () => {
      const response = await api(`/api/runs/${run.run_id}/rollback`, { method: "POST" });
      toast(`回滚批次：${response.run_id}`);
      await refreshRuns();
    });
    const row = document.createElement("tr");
    row.append(cellText(run.run_id), cellText(run.timestamp), cellText(run.status), cellText(JSON.stringify(run.summary)), cell(button));
    body.append(row);
  }
}

function setupTabs() {
  for (const button of document.querySelectorAll("nav button")) {
    button.addEventListener("click", () => {
      for (const item of document.querySelectorAll("nav button")) item.classList.remove("active");
      for (const panel of document.querySelectorAll(".panel")) panel.classList.remove("active");
      button.classList.add("active");
      document.querySelector(`[data-panel="${button.dataset.tab}"]`).classList.add("active");
    });
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  setupTabs();
  $("#scanBtn").addEventListener("click", () => scan().catch((error) => toast(error.message)));
  $("#planBtn").addEventListener("click", () => plan().catch((error) => toast(error.message)));
  $("#llmBtn").addEventListener("click", () => llmSuggest().catch((error) => toast(error.message)));
  $("#executeBtn").addEventListener("click", () => executeSelected().catch((error) => toast(error.message)));
  $("#refreshRunsBtn").addEventListener("click", () => refreshRuns().catch((error) => toast(error.message)));
  $("#saveSettingsBtn").addEventListener("click", () => saveSettings().catch((error) => toast(error.message)));
  await loadSettings().catch((error) => toast(error.message));
  await refreshRuns().catch(() => {});
});

