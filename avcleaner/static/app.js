const state = {
  settings: null,
  scan: null,
  plan: null,
  llmSuggestions: [],
  filter: "all",
};

const $ = (selector) => document.querySelector(selector);
const apiToken = document.querySelector('meta[name="avcleaner-token"]')?.content || "";

function toast(message) {
  const node = $("#toast");
  node.textContent = message;
  node.classList.add("show");
  window.setTimeout(() => node.classList.remove("show"), 2600);
}

function downloadText(filename, text, type) {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      "X-AVCleaner-Token": apiToken,
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error_code || body.detail || "operation_failed");
  }
  return response.json();
}

async function apiText(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      "X-AVCleaner-Token": apiToken,
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error_code || body.detail || "operation_failed");
  }
  return response.text();
}

function updateSummary() {
  const items = state.plan?.items || [];
  const summary = state.plan?.summary || {};
  const blocking = summary.blocking_items ?? items.filter((item) => hasBlocking(item)).length;
  $("#metricFiles").textContent = state.scan?.total_files || 0;
  $("#metricRename").textContent = summary.rename_items ?? items.filter((item) => item.action === "rename").length;
  $("#metricReview").textContent = summary.requires_review_items ?? items.filter((item) => item.action === "review").length;
  $("#metricTrash").textContent = summary.quarantine_items ?? items.filter((item) => item.action === "quarantine").length;
  $("#scanId").textContent = state.scan?.scan_id || "-";
  $("#planId").textContent = state.plan?.plan_id || "-";
  $("#planHash").textContent = state.plan?.plan_hash ? `${state.plan.plan_hash.slice(0, 12)}...` : "-";
  $("#blockingCount").textContent = blocking;
  $("#executeBtn").disabled = !state.plan || selectedExecutableItems().length === 0;
}

function hasBlocking(item) {
  return (item.issues || []).some((issue) => issue.blocking);
}

function hasWarningOnly(item) {
  return (item.issues || []).length > 0 && !hasBlocking(item);
}

function selectedExecutableItems() {
  return (state.plan?.items || []).filter((item) => item.selected && ["rename", "quarantine"].includes(item.action));
}

function filteredItems() {
  const items = state.plan?.items || [];
  if (state.filter === "selected") return items.filter((item) => item.selected);
  if (state.filter === "safe_selectable") return items.filter((item) => !item.blocking && !item.requires_review && !item.sidecar_type && ["rename", "quarantine"].includes(item.action));
  if (state.filter === "blocking") return items.filter(hasBlocking);
  if (state.filter === "warning") return items.filter(hasWarningOnly);
  if (state.filter === "requires_review") return items.filter((item) => item.requires_review);
  if (state.filter === "conflict") return items.filter((item) => (item.review_buckets || []).includes("conflict"));
  if (state.filter === "sidecar") return items.filter((item) => item.sidecar_type);
  if (state.filter === "junk_candidate") return items.filter((item) => item.action === "quarantine" || (item.review_buckets || []).includes("junk_candidate"));
  if (state.filter === "manual_edited") return items.filter((item) => item.manual_edited);
  return items;
}

function renderPlan() {
  const body = $("#planBody");
  body.innerHTML = "";
  for (const item of filteredItems()) {
    const row = document.createElement("tr");
    row.dataset.id = item.id;

    const checked = document.createElement("input");
    checked.type = "checkbox";
    checked.checked = item.selected;
    checked.disabled = !["rename", "quarantine"].includes(item.action) || item.blocking || item.selection_locked;
    checked.addEventListener("change", () => {
      updateSelection(checked.checked ? "add" : "remove", [item.id]).catch((error) => {
        toast(error.message);
        renderPlan();
      });
    });

    const nameInput = document.createElement("input");
    nameInput.className = "name-input";
    nameInput.value = item.target_name || item.suggested_name;
    nameInput.disabled = item.action === "quarantine" || item.action === "keep";
    nameInput.addEventListener("change", async () => {
      if (!state.plan?.plan_id) return;
      const response = await api(`/api/plans/${state.plan.plan_id}/items/${item.id}`, {
        method: "PATCH",
        body: JSON.stringify({ target_name: nameInput.value }),
      });
      state.plan.plan_hash = response.plan_hash;
      state.plan.summary = response.summary;
      for (const affected of response.affected_items) {
        const index = state.plan.items.findIndex((rowItem) => rowItem.id === affected.id);
        if (index >= 0) state.plan.items[index] = affected;
      }
      const editedIndex = state.plan.items.findIndex((rowItem) => rowItem.id === response.item.id);
      if (editedIndex >= 0) state.plan.items[editedIndex] = response.item;
      renderPlan();
    });

    row.append(
      cell(checked),
      cell(pill(item.action, hasBlocking(item))),
      cellText(item.original_name),
      cell(nameInput),
      cellText(item.source || item.suggestion_source || ""),
      cellText(Number(item.confidence || 0).toFixed(2)),
      cellText(item.reason),
      cellIssues(item.issues || item.warnings || []),
      cellText(groupLabel(item)),
      cellBadges(item),
      cellLlmSuggestion(item),
      cellTrace(item)
    );
    body.append(row);
    if (item._traceOpen) body.append(traceRow(item));
  }
  renderTrash();
  updateSummary();
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

function cellIssues(issues) {
  const td = document.createElement("td");
  const codes = issues.map((issue) => (typeof issue === "string" ? issue : issue.code));
  td.className = issues.some((issue) => typeof issue !== "string" && issue.blocking) ? "error" : "warning";
  td.textContent = codes.join("; ");
  return td;
}

function cellTrace(item) {
  const button = document.createElement("button");
  button.textContent = "Trace";
  button.disabled = !(item.trace || []).length;
  button.addEventListener("click", () => {
    item._traceOpen = !item._traceOpen;
    renderPlan();
  });
  return cell(button);
}

function groupLabel(item) {
  return item.group_id ? `${item.associated_media_code || item.media_code || "group"}:${item.group_id.slice(-6)}` : "";
}

function sidecarLabel(item) {
  if (!item.sidecar_type) return "";
  const parts = [item.sidecar_type];
  if (item.language_suffix) parts.push(item.language_suffix);
  if (item.selected_default === false) parts.push("default:off");
  return parts.join(" ");
}

function cellBadges(item) {
  const td = document.createElement("td");
  const badges = [];
  if (item.blocking) badges.push("blocking");
  if (item.warning_count) badges.push("warning");
  if (item.requires_review) badges.push("review");
  if (item.sidecar_type) badges.push(sidecarLabel(item));
  if (item.manual_edited) badges.push("manual");
  td.textContent = badges.join(" | ");
  return td;
}

function latestSuggestionFor(item) {
  return (state.llmSuggestions || []).find((suggestion) => suggestion.item_id === item.id && !["rejected", "stale"].includes(suggestion.status));
}

function cellLlmSuggestion(item) {
  const td = document.createElement("td");
  const suggestion = latestSuggestionFor(item);
  if (!suggestion) {
    td.textContent = "";
    return td;
  }
  const summary = document.createElement("div");
  summary.className = "llm-suggestion";
  summary.textContent = `${suggestion.suggested_name} | ${Number(suggestion.confidence || 0).toFixed(2)} | ${suggestion.status}`;
  td.append(summary);
  if (suggestion.reason) {
    const reason = document.createElement("div");
    reason.className = "muted";
    reason.textContent = suggestion.reason;
    td.append(reason);
  }
  if ((suggestion.validation_issues || []).length) {
    const issues = document.createElement("div");
    issues.className = "error";
    issues.textContent = suggestion.validation_issues.map((issue) => issue.code).join("; ");
    td.append(issues);
  }
  const accept = document.createElement("button");
  accept.textContent = "Accept";
  accept.disabled = suggestion.status !== "valid";
  accept.addEventListener("click", () => acceptLlmSuggestion(suggestion).catch((error) => toast(error.message)));
  const reject = document.createElement("button");
  reject.textContent = "Reject";
  reject.addEventListener("click", () => rejectLlmSuggestion(suggestion).catch((error) => toast(error.message)));
  td.append(accept, reject);
  return td;
}

function traceRow(item) {
  const row = document.createElement("tr");
  row.className = "trace-row";
  const td = document.createElement("td");
  td.colSpan = 12;
  const list = document.createElement("div");
  list.className = "trace-list";
  for (const step of item.trace || []) {
    const node = document.createElement("div");
    node.className = "trace-step";
    node.textContent = [
      step.rule_id,
      `before=${step.before || ""}`,
      `after=${step.after || ""}`,
      `removed=${(step.removed_tokens || []).join(",")}`,
      `preserved=${(step.preserved_tokens || []).join(",")}`,
      `warnings=${(step.warnings || []).join(",")}`,
    ].join(" | ");
    list.append(node);
  }
  td.append(list);
  row.append(td);
  return row;
}

function pill(action, blocking) {
  const span = document.createElement("span");
  span.className = `pill ${blocking ? "review" : action}`;
  span.textContent = blocking ? "blocked" : action;
  return span;
}

function formatSize(bytes) {
  if (!bytes) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function linesFromTextarea(selector) {
  return ($(selector).value || "")
    .split(/\r?\n/)
    .map((value) => value.trim())
    .filter(Boolean);
}

function setTextareaLines(selector, values) {
  $(selector).value = (values || []).join("\n");
}

function syncRuleFormFromSettings() {
  const rules = state.settings.rules || {};
  $("#ruleOutputTemplate").value = rules.output_template || "{code}{part}{variant}{language}{ext}";
  setTextareaLines("#ruleRemoveAdDomains", rules.remove_ad_domains || []);
  setTextareaLines("#ruleRemoveNoiseTokens", rules.remove_noise_tokens || []);
  $("#rulePreserveSidecarLanguage").checked = rules.preserve_sidecar_language !== false;
  $("#rulePreserveVariant").checked = rules.preserve_variant !== false;
  $("#rulePreservePartSuffix").checked = rules.preserve_part_suffix !== false;
  $("#ruleReviewThreshold").value = rules.review_threshold ?? 0.7;
}

function syncRuleFormToSettings() {
  state.settings.rules = state.settings.rules || {};
  state.settings.rules.output_template = $("#ruleOutputTemplate").value.trim() || "{code}{part}{variant}{language}{ext}";
  state.settings.rules.remove_ad_domains = linesFromTextarea("#ruleRemoveAdDomains");
  state.settings.rules.remove_noise_tokens = linesFromTextarea("#ruleRemoveNoiseTokens");
  state.settings.rules.preserve_sidecar_language = $("#rulePreserveSidecarLanguage").checked;
  state.settings.rules.preserve_variant = $("#rulePreserveVariant").checked;
  state.settings.rules.preserve_part_suffix = $("#rulePreservePartSuffix").checked;
  state.settings.rules.review_threshold = Number($("#ruleReviewThreshold").value || 0.7);
}

async function loadSettings() {
  state.settings = await api("/api/settings");
  $("#llmProvider").value = state.settings.llm.provider;
  $("#llmBaseUrl").value = state.settings.llm.base_url;
  $("#llmModel").value = state.settings.llm.model;
  $("#llmApiKey").value = state.settings.llm.api_key || "";
  $("#llmSendPath").checked = state.settings.llm.send_full_path;
  syncRuleFormFromSettings();
}

async function saveSettings() {
  syncRuleFormToSettings();
  state.settings.llm.provider = $("#llmProvider").value;
  state.settings.llm.base_url = $("#llmBaseUrl").value;
  state.settings.llm.model = $("#llmModel").value;
  state.settings.llm.api_key = $("#llmApiKey").value;
  state.settings.llm.send_full_path = $("#llmSendPath").checked;
  state.settings = await api("/api/settings", {
    method: "PUT",
    body: JSON.stringify(state.settings),
  });
  $("#llmApiKey").value = "";
  toast("settings_saved");
}

async function testLlm() {
  const response = await api("/api/llm/test", {
    method: "POST",
    body: JSON.stringify({}),
  });
  $("#llmTestResult").textContent = JSON.stringify(response, null, 2);
}

async function testRules() {
  const filename = $("#ruleTestFilename").value.trim();
  if (!filename) {
    toast("filename_required");
    return;
  }
  const response = await api("/api/rules/test", {
    method: "POST",
    body: JSON.stringify({
      filename,
      settings_override: {
        output_template: $("#ruleOutputTemplate").value.trim() || "{code}{part}{variant}{language}{ext}",
        remove_ad_domains: linesFromTextarea("#ruleRemoveAdDomains"),
        remove_noise_tokens: linesFromTextarea("#ruleRemoveNoiseTokens"),
        preserve_sidecar_language: $("#rulePreserveSidecarLanguage").checked,
        preserve_variant: $("#rulePreserveVariant").checked,
        preserve_part_suffix: $("#rulePreservePartSuffix").checked,
        review_threshold: Number($("#ruleReviewThreshold").value || 0.7),
      },
    }),
  });
  $("#ruleTestResult").textContent = JSON.stringify(response, null, 2);
}

async function exportSettings() {
  const response = await api("/api/settings/export");
  const text = JSON.stringify(response, null, 2);
  $("#settingsExportResult").textContent = text;
  $("#settingsImportPayload").value = JSON.stringify(response.settings, null, 2);
}

async function importSettings(dryRun) {
  const raw = $("#settingsImportPayload").value.trim();
  if (!raw) {
    toast("settings_import_required");
    return;
  }
  const response = await api("/api/settings/import", {
    method: "POST",
    body: JSON.stringify({ settings: JSON.parse(raw), dry_run: dryRun }),
  });
  $("#settingsImportResult").textContent = JSON.stringify(response, null, 2);
  if (!dryRun && response.settings) {
    await loadSettings();
  }
}

async function scan() {
  const root = $("#rootPath").value.trim();
  if (!root) {
    toast("root_required");
    return;
  }
  state.scan = await api("/api/scan", {
    method: "POST",
    body: JSON.stringify({ root_path: root, recursive: true }),
  });
  state.plan = null;
  state.llmSuggestions = [];
  renderPlan();
  toast(`scan_complete:${state.scan.total_files}`);
}

async function plan() {
  if (!state.scan) await scan();
  state.plan = await api("/api/plans", {
    method: "POST",
    body: JSON.stringify({ scan_id: state.scan.scan_id }),
  });
  state.llmSuggestions = [];
  renderPlan();
  toast("plan_created");
}

async function validatePlan() {
  if (!state.plan?.plan_id) {
    toast("plan_required");
    return;
  }
  state.plan = await api(`/api/plans/${state.plan.plan_id}/validate`, { method: "POST" });
  renderPlan();
  toast("plan_validated");
}

async function updateSelection(mode, itemIds = []) {
  if (!state.plan?.plan_id) {
    toast("plan_required");
    return;
  }
  const response = await api(`/api/plans/${state.plan.plan_id}/selection`, {
    method: "PATCH",
    body: JSON.stringify({ mode, selected_item_ids: itemIds }),
  });
  state.plan.plan_hash = response.plan_hash;
  state.plan.summary = response.summary;
  state.plan.items = response.items || state.plan.items.map((item) => ({
    ...item,
    selected: response.selected_item_ids.includes(item.id),
    checked: response.selected_item_ids.includes(item.id),
  }));
  renderPlan();
}

async function selectSafeItems() {
  await updateSelection("select_safe", []);
  toast("safe_items_selected");
}

async function clearSelection() {
  await updateSelection("replace", []);
  toast("selection_cleared");
}

async function showExecutionSummary() {
  if (!state.plan?.plan_id) {
    toast("plan_required");
    return null;
  }
  const selected = selectedExecutableItems();
  const response = await api(`/api/plans/${state.plan.plan_id}/execution-summary`, {
    method: "POST",
    body: JSON.stringify({
      selected_item_ids: selected.map((item) => item.id),
      plan_hash: state.plan.plan_hash,
    }),
  });
  const target = $("#executionSummaryResult");
  if (target) target.textContent = JSON.stringify(response, null, 2);
  return response;
}

function llmReviewItemIds() {
  const selected = selectedExecutableItems().map((item) => item.id);
  if (selected.length) return selected;
  return (state.plan?.items || [])
    .filter((item) => item.requires_review || item.action === "review")
    .map((item) => item.id);
}

async function previewLlmPayload() {
  if (!state.plan?.plan_id) {
    toast("plan_required");
    return;
  }
  const itemIds = llmReviewItemIds();
  if (!itemIds.length) {
    toast("no_llm_items");
    return;
  }
  const response = await api(`/api/plans/${state.plan.plan_id}/llm/payload-preview`, {
    method: "POST",
    body: JSON.stringify({ item_ids: itemIds, include_neighbors: true }),
  });
  const target = $("#executionSummaryResult");
  if (target) target.textContent = JSON.stringify(response, null, 2);
}

async function loadLlmSuggestions() {
  if (!state.plan?.plan_id) return;
  const response = await api(`/api/plans/${state.plan.plan_id}/llm/suggestions`);
  state.llmSuggestions = response.suggestions || [];
}

async function exportPlanJson() {
  if (!state.plan?.plan_id) {
    toast("plan_required");
    return;
  }
  const response = await api(`/api/plans/${state.plan.plan_id}/export.json`);
  const text = JSON.stringify(response, null, 2);
  const target = $("#executionSummaryResult");
  if (target) target.textContent = text;
  downloadText(`${state.plan.plan_id}.json`, text, "application/json");
}

async function exportPlanCsv() {
  if (!state.plan?.plan_id) {
    toast("plan_required");
    return;
  }
  const response = await apiText(`/api/plans/${state.plan.plan_id}/export.csv`);
  const target = $("#executionSummaryResult");
  if (target) target.textContent = response;
  downloadText(`${state.plan.plan_id}.csv`, response, "text/csv");
}

async function llmSuggest() {
  if (!state.plan) await plan();
  const itemIds = llmReviewItemIds();
  if (!itemIds.length) {
    toast("no_llm_items");
    return;
  }
  const response = await api(`/api/plans/${state.plan.plan_id}/llm/suggest`, {
    method: "POST",
    body: JSON.stringify({
      item_ids: itemIds,
      include_neighbors: true,
      use_cache: true,
    }),
  });
  state.llmSuggestions = response.suggestions || [];
  renderPlan();
  toast(`llm_suggestions:${response.suggestions.length}`);
}

async function acceptLlmSuggestion(suggestion) {
  if (!state.plan?.plan_id) return;
  const response = await api(`/api/plans/${state.plan.plan_id}/llm/suggestions/${suggestion.suggestion_id}/accept`, {
    method: "POST",
    body: JSON.stringify({ expected_plan_hash: state.plan.plan_hash }),
  });
  state.plan.plan_hash = response.plan_hash;
  state.plan.summary = response.summary;
  const itemIndex = state.plan.items.findIndex((item) => item.id === response.item.id);
  if (itemIndex >= 0) state.plan.items[itemIndex] = response.item;
  await loadLlmSuggestions();
  renderPlan();
}

async function rejectLlmSuggestion(suggestion) {
  if (!state.plan?.plan_id) return;
  await api(`/api/plans/${state.plan.plan_id}/llm/suggestions/${suggestion.suggestion_id}/reject`, {
    method: "POST",
    body: JSON.stringify({ reason_code: "user_rejected" }),
  });
  await loadLlmSuggestions();
  renderPlan();
}

async function executeSelected() {
  const selected = selectedExecutableItems();
  if (!state.plan || !selected.length) {
    toast("nothing_selected");
    return;
  }
  const summary = await showExecutionSummary();
  if (!summary?.ok_to_execute) {
    toast("execution_summary_blocked");
    return;
  }
  if (!window.confirm(`Execute ${summary.selected_count} selected item(s)?`)) return;
  const response = await api(`/api/plans/${state.plan.plan_id}/execute`, {
    method: "POST",
    body: JSON.stringify({
      selected_item_ids: selected.map((item) => item.id),
      confirm: true,
      plan_hash: state.plan.plan_hash,
    }),
  });
  toast(`run:${response.run_id}`);
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
    button.textContent = "rollback";
    button.addEventListener("click", async () => {
      const response = await api(`/api/runs/${run.run_id}/rollback`, { method: "POST" });
      toast(`rollback:${response.run_id}`);
      await refreshRuns();
    });
    const row = document.createElement("tr");
    row.append(cellText(run.run_id), cellText(run.timestamp), cellText(run.state || run.status), cellText(JSON.stringify(run.summary)), cell(button));
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

function setupReviewControls() {
  const filter = $("#filterSelect");
  if (filter) {
    filter.innerHTML = "";
    for (const [value, label] of [
      ["all", "all"],
      ["selected", "selected"],
      ["safe_selectable", "safe selectable"],
      ["blocking", "blocking"],
      ["warning", "warnings"],
      ["requires_review", "requires review"],
      ["conflict", "conflicts"],
      ["sidecar", "sidecars"],
      ["junk_candidate", "junk candidates"],
      ["manual_edited", "manual edits"],
    ]) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      filter.append(option);
    }
  }
  const summary = document.querySelector(".plan-summary");
  if (!summary || $("#selectSafeBtn")) return;
  for (const [id, label] of [
    ["selectSafeBtn", "Select safe items"],
    ["clearSelectionBtn", "Clear selection"],
    ["exportPlanJsonBtn", "Export JSON"],
    ["exportPlanCsvBtn", "Export CSV"],
    ["executionSummaryBtn", "Show execution summary"],
    ["previewLlmPayloadBtn", "Preview LLM payload"],
    ["getLlmSuggestionsBtn", "Get LLM suggestions"],
  ]) {
    const button = document.createElement("button");
    button.id = id;
    button.textContent = label;
    summary.append(button);
  }
  const pre = document.createElement("pre");
  pre.id = "executionSummaryResult";
  pre.className = "test-result";
  summary.append(pre);
}

document.addEventListener("DOMContentLoaded", async () => {
  setupTabs();
  setupReviewControls();
  $("#filterSelect").addEventListener("change", () => {
    state.filter = $("#filterSelect").value;
    renderPlan();
  });
  $("#scanBtn").addEventListener("click", () => scan().catch((error) => toast(error.message)));
  $("#planBtn").addEventListener("click", () => plan().catch((error) => toast(error.message)));
  $("#validateBtn").addEventListener("click", () => validatePlan().catch((error) => toast(error.message)));
  $("#llmBtn").addEventListener("click", () => llmSuggest().catch((error) => toast(error.message)));
  $("#executeBtn").addEventListener("click", () => executeSelected().catch((error) => toast(error.message)));
  $("#selectSafeBtn").addEventListener("click", () => selectSafeItems().catch((error) => toast(error.message)));
  $("#clearSelectionBtn").addEventListener("click", () => clearSelection().catch((error) => toast(error.message)));
  $("#exportPlanJsonBtn").addEventListener("click", () => exportPlanJson().catch((error) => toast(error.message)));
  $("#exportPlanCsvBtn").addEventListener("click", () => exportPlanCsv().catch((error) => toast(error.message)));
  $("#executionSummaryBtn").addEventListener("click", () => showExecutionSummary().catch((error) => toast(error.message)));
  $("#previewLlmPayloadBtn").addEventListener("click", () => previewLlmPayload().catch((error) => toast(error.message)));
  $("#getLlmSuggestionsBtn").addEventListener("click", () => llmSuggest().catch((error) => toast(error.message)));
  $("#refreshRunsBtn").addEventListener("click", () => refreshRuns().catch((error) => toast(error.message)));
  $("#saveSettingsBtn").addEventListener("click", () => saveSettings().catch((error) => toast(error.message)));
  $("#testLlmBtn").addEventListener("click", () => testLlm().catch((error) => toast(error.message)));
  $("#testRuleBtn").addEventListener("click", () => testRules().catch((error) => toast(error.message)));
  $("#exportSettingsBtn").addEventListener("click", () => exportSettings().catch((error) => toast(error.message)));
  $("#importSettingsDryRunBtn").addEventListener("click", () => importSettings(true).catch((error) => toast(error.message)));
  $("#applyImportSettingsBtn").addEventListener("click", () => importSettings(false).catch((error) => toast(error.message)));
  await loadSettings().catch((error) => toast(error.message));
  await refreshRuns().catch(() => {});
  updateSummary();
});
