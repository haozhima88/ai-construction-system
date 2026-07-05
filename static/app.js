const state = {
  limit: 50,
  offset: 0,
  total: 0,
  records: [],
  selected: new Set(),
};

const statusLabels = {
  pending: "待验收",
  approved: "已通过",
  rejected: "已驳回",
  needs_fix: "需修正",
  parsed: "parsed",
  warning: "warning",
  error: "error",
};

function $(id) {
  return document.getElementById(id);
}

function showMessage(text, type = "error") {
  const message = $("message");
  message.textContent = text;
  message.className = `message ${type}`;
  message.hidden = !text;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatNumber(value) {
  if (value === null || value === undefined || value === "") return "";
  return Number(value).toLocaleString("zh-CN", { maximumFractionDigits: 4 });
}

function badge(status) {
  const value = status || "pending";
  return `<span class="badge badge-${escapeHtml(value)}">${escapeHtml(statusLabels[value] || value)}</span>`;
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.success === false) {
    throw new Error(data.detail || data.message || `请求失败: ${response.status}`);
  }
  return data;
}

function recordsUrl() {
  const params = new URLSearchParams();
  params.set("limit", state.limit);
  params.set("offset", state.offset);

  const parseStatus = $("parseStatus").value;
  const reviewStatus = $("reviewStatus").value;
  const keyword = $("keyword").value.trim();

  if (parseStatus) params.set("parse_status", parseStatus);
  if (reviewStatus) params.set("review_status", reviewStatus);
  if (keyword) params.set("keyword", keyword);

  return `/import-review/records?${params.toString()}`;
}

async function loadStats() {
  const data = await requestJson("/import-review/stats");
  const stats = [
    ["总记录数", data.total],
    ["parsed", data.by_parse_status?.parsed || 0],
    ["warning", data.by_parse_status?.warning || 0],
    ["error", data.by_parse_status?.error || 0],
    ["pending", data.by_review_status?.pending || 0],
    ["approved", data.by_review_status?.approved || 0],
    ["rejected", data.by_review_status?.rejected || 0],
    ["needs_fix", data.by_review_status?.needs_fix || 0],
  ];

  $("statsGrid").innerHTML = stats
    .map(([label, value]) => `
      <article class="stat-card">
        <span>${escapeHtml(label)}</span>
        <strong>${formatNumber(value)}</strong>
      </article>
    `)
    .join("");
}

async function loadRecords() {
  const data = await requestJson(recordsUrl());
  state.records = data.records || [];
  state.total = data.total || 0;
  state.limit = data.limit || state.limit;
  state.offset = data.offset || 0;
  state.selected.clear();
  renderTable();
  renderPager();
  renderSelection();
}

function renderTable() {
  const body = $("recordsBody");
  const empty = $("emptyState");
  empty.hidden = state.records.length > 0;
  body.innerHTML = state.records.map((record) => `
    <tr data-id="${record.id}">
      <td><input class="row-check" type="checkbox" value="${record.id}"></td>
      <td class="id-cell">${escapeHtml(record.id)}</td>
      <td class="row-no-cell">${escapeHtml(record.source_excel_row_no)}</td>
      <td>${badge(record.review_status)}</td>
      <td>${badge(record.parse_status)}</td>
      <td class="code-cell">${escapeHtml(record.item_code)}</td>
      <td class="name-cell" title="${escapeHtml(record.item_name)}">${escapeHtml(record.item_name)}</td>
      <td class="feature-cell" title="${escapeHtml(record.feature)}">${escapeHtml(record.feature)}</td>
      <td class="unit-cell">${escapeHtml(record.unit)}</td>
      <td class="number">${formatNumber(record.quantity)}</td>
      <td class="number">${formatNumber(record.unit_price)}</td>
      <td class="number">${formatNumber(record.total_price)}</td>
      <td class="category-cell" title="${escapeHtml(record.category)}">${escapeHtml(record.category)}</td>
      <td class="source-cell" title="${escapeHtml(record.source_file_name)}">${escapeHtml(record.source_file_name)}</td>
      <td class="sheet-cell" title="${escapeHtml(record.source_sheet_name)}">${escapeHtml(record.source_sheet_name)}</td>
      <td class="warning-text" title="${escapeHtml(record.parse_warnings)}">${escapeHtml(record.parse_warnings)}</td>
      <td class="actions">
        <button data-id="${record.id}" data-status="approved" type="button">通过</button>
        <button data-id="${record.id}" data-status="rejected" class="danger" type="button">驳回</button>
        <button data-id="${record.id}" data-status="needs_fix" class="warning" type="button">需修正</button>
        <button data-id="${record.id}" data-status="pending" class="secondary" type="button">待验收</button>
      </td>
    </tr>
  `).join("");
  $("selectAll").checked = false;
}

function renderPager() {
  $("pageInfo").textContent = `offset ${state.offset} / limit ${state.limit}`;
  $("countInfo").textContent = `当前页 ${state.records.length} 条 / 总计 ${state.total} 条`;
  $("prevBtn").disabled = state.offset <= 0;
  $("nextBtn").disabled = state.offset + state.limit >= state.total;
}

function renderSelection() {
  $("selectedCount").textContent = `已选 ${state.selected.size} 条`;
}

async function refreshAll() {
  showMessage("");
  const results = await Promise.allSettled([loadStats(), loadRecords()]);
  const errors = results
    .filter((result) => result.status === "rejected")
    .map((result) => result.reason?.message || "请求失败");

  if (errors.length > 0) {
    showMessage(errors.join("；"));
  }
}

async function reloadRecordsOnly() {
  showMessage("");
  await loadRecords();
}

async function updateOne(id, reviewStatus) {
  await requestJson(`/import-review/records/${id}/review-status`, {
    method: "PATCH",
    body: JSON.stringify({ review_status: reviewStatus }),
  });
  await refreshAll();
}

async function updateBulk(reviewStatus) {
  const recordIds = Array.from(state.selected).map((value) => Number(value));
  if (recordIds.length === 0) {
    showMessage("请先选择需要批量处理的记录");
    return;
  }
  await requestJson("/import-review/records/bulk-review-status", {
    method: "POST",
    body: JSON.stringify({ record_ids: recordIds, review_status: reviewStatus }),
  });
  await refreshAll();
}

function bindEvents() {
  document.addEventListener("click", async (event) => {
    const actionButton = event.target.closest(".actions button");
    const bulkButton = event.target.closest("[data-bulk-status]");
    try {
      if (actionButton) {
        await updateOne(actionButton.dataset.id, actionButton.dataset.status);
      } else if (bulkButton) {
        await updateBulk(bulkButton.dataset.bulkStatus);
      }
    } catch (error) {
      showMessage(error.message);
    }
  });

  $("recordsBody").addEventListener("change", (event) => {
    if (!event.target.classList.contains("row-check")) return;
    if (event.target.checked) {
      state.selected.add(event.target.value);
    } else {
      state.selected.delete(event.target.value);
    }
    renderSelection();
  });

  $("selectAll").addEventListener("change", (event) => {
    state.selected.clear();
    document.querySelectorAll(".row-check").forEach((checkbox) => {
      checkbox.checked = event.target.checked;
      if (checkbox.checked) state.selected.add(checkbox.value);
    });
    renderSelection();
  });

  $("searchBtn").addEventListener("click", async () => {
    state.offset = 0;
    try {
      await reloadRecordsOnly();
    } catch (error) {
      showMessage(error.message);
    }
  });

  $("resetBtn").addEventListener("click", async () => {
    $("parseStatus").value = "";
    $("reviewStatus").value = "";
    $("keyword").value = "";
    state.offset = 0;
    try {
      await reloadRecordsOnly();
    } catch (error) {
      showMessage(error.message);
    }
  });

  $("prevBtn").addEventListener("click", async () => {
    state.offset = Math.max(0, state.offset - state.limit);
    try {
      await reloadRecordsOnly();
    } catch (error) {
      showMessage(error.message);
    }
  });

  $("nextBtn").addEventListener("click", async () => {
    state.offset += state.limit;
    try {
      await reloadRecordsOnly();
    } catch (error) {
      showMessage(error.message);
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  bindEvents();
  refreshAll();
});
