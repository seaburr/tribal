// ── State ─────────────────────────────────────────────────────────────────────
let resources = [];
let eventsByDate = {};
let calYear, calMonth;
let calViewMode = 'month'; // 'month' | 'year'
let editingId = null;
let deletingId = null;
let deletingName = null;
let detailResourceId = null;
let sortCol = "expiration_date";
let sortDir = 1;

const MONTH_NAMES = ["January","February","March","April","May","June",
                     "July","August","September","October","November","December"];

// ── Init ──────────────────────────────────────────────────────────────────────
(function init() {
  const now = new Date();
  calYear = now.getFullYear();
  calMonth = now.getMonth();
  loadData();
})();

async function loadData() {
  try {
    const res = await fetch("/api/resources/");
    resources = await res.json();
  } catch (e) {
    resources = [];
  }

  eventsByDate = {};
  resources.forEach(r => {
    if (!eventsByDate[r.expiration_date]) eventsByDate[r.expiration_date] = [];
    eventsByDate[r.expiration_date].push(r);
  });

  renderCalendar();
  renderUpcoming();
  renderTable();
}

// ── Tab switching ─────────────────────────────────────────────────────────────
function switchTab(name) {
  document.querySelectorAll(".tab").forEach(t => {
    t.classList.toggle("active", t.dataset.tab === name);
  });
  document.querySelectorAll(".tab-pane").forEach(p => {
    p.classList.toggle("active", p.id === "tab-" + name);
  });
}

// ── Date helpers ──────────────────────────────────────────────────────────────
function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;
}

function pad(n) { return String(n).padStart(2, "0"); }

function isoToDisplay(iso) {
  const [y, m, d] = iso.split("-");
  return `${m}/${d}/${y}`;
}

function daysUntil(isoDate) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const expiry = new Date(isoDate + "T00:00:00");
  return Math.round((expiry - today) / 86400000);
}

function urgencyClass(days) {
  if (days < 0)   return "evt-overdue";
  if (days <= 7)  return "evt-red";
  if (days <= 14) return "evt-orange";
  if (days <= 30) return "evt-amber";
  return "evt-green";
}

function statusBadge(isoDate) {
  const days = daysUntil(isoDate);
  if (days < 0)   return `<span class="badge badge-red">Expired</span>`;
  if (days === 0) return `<span class="badge badge-red">Expires today</span>`;
  if (days <= 3)  return `<span class="badge badge-red">URGENT &mdash; ${days}d</span>`;
  if (days <= 7)  return `<span class="badge badge-red">${days} days</span>`;
  if (days <= 14) return `<span class="badge badge-orange">${days} days</span>`;
  if (days <= 30) return `<span class="badge badge-amber">${days} days</span>`;
  return `<span class="badge badge-green">${days} days</span>`;
}

// ── Linkify ───────────────────────────────────────────────────────────────────
function linkify(text) {
  const urlPattern = /(https?:\/\/[^\s]+)/g;
  return text.split(urlPattern).map((part, i) => {
    if (i % 2 === 1) {
      const url = part.replace(/[.,;:!?)]+$/, '');
      const trailing = part.slice(url.length);
      return `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(url)}</a>${esc(trailing)}`;
    }
    return esc(part);
  }).join('');
}

// ── Calendar (month view) ─────────────────────────────────────────────────────
function renderCalendar() {
  const weekdaysEl = document.getElementById("cal-weekdays");
  const toggleBtn  = document.getElementById("cal-view-toggle");

  if (calViewMode === 'year') {
    weekdaysEl.style.display = "none";
    toggleBtn.textContent = "Month View";
    renderYearView();
    return;
  }

  // Month view
  weekdaysEl.style.display = "grid";
  toggleBtn.textContent = "Year View";

  document.getElementById("cal-title").textContent = `${MONTH_NAMES[calMonth]} ${calYear}`;

  const today = todayISO();
  const firstDay = new Date(calYear, calMonth, 1).getDay();
  const daysInMonth = new Date(calYear, calMonth + 1, 0).getDate();

  let html = "";
  for (let i = 0; i < firstDay; i++) html += `<div class="cal-cell empty"></div>`;

  for (let day = 1; day <= daysInMonth; day++) {
    const iso = `${calYear}-${pad(calMonth+1)}-${pad(day)}`;
    const events = eventsByDate[iso] || [];
    const isToday = iso === today;

    let cls = "cal-cell";
    if (events.length) cls += " has-event " + urgencyClass(daysUntil(iso));
    if (isToday) cls += " today";

    const onclick = events.length ? `onCalDateClick('${iso}')` : "";
    const title = events.length ? esc(events.map(r => r.name).join(", ")) : "";
    html += `<div class="${cls}" onclick="${onclick}" title="${title}">${day}</div>`;
  }

  document.getElementById("cal-body").innerHTML = html;
}

// ── Calendar (year view) ──────────────────────────────────────────────────────
function renderYearView() {
  document.getElementById("cal-title").textContent = calYear;

  const today = todayISO();
  let html = '<div class="year-grid">';

  for (let m = 0; m < 12; m++) {
    const firstDay = new Date(calYear, m, 1).getDay();
    const daysInMonth = new Date(calYear, m + 1, 0).getDate();

    html += `<div class="mini-month">`;
    html += `<div class="mini-month-header">${MONTH_NAMES[m]}</div>`;
    html += `<div class="mini-cal-weekdays">`;
    for (const d of ['S','M','T','W','T','F','S']) {
      html += `<div class="mini-cal-weekday">${d}</div>`;
    }
    html += `</div><div class="mini-cal-body">`;

    for (let i = 0; i < firstDay; i++) html += `<div class="mini-cell empty"></div>`;

    for (let day = 1; day <= daysInMonth; day++) {
      const iso = `${calYear}-${pad(m+1)}-${pad(day)}`;
      const events = eventsByDate[iso] || [];
      const isToday = iso === today;

      let cls = "mini-cell";
      if (events.length) cls += " has-event " + urgencyClass(daysUntil(iso));
      if (isToday) cls += " today";

      const onclick = events.length ? `onCalDateClick('${iso}')` : "";
      const title = events.length ? esc(events.map(r => r.name).join(", ")) : "";
      html += `<div class="${cls}" onclick="${onclick}" title="${title}">${day}</div>`;
    }

    html += `</div></div>`; // mini-cal-body, mini-month
  }

  html += '</div>'; // year-grid
  document.getElementById("cal-body").innerHTML = html;
}

function toggleYearView() {
  calViewMode = calViewMode === 'month' ? 'year' : 'month';
  renderCalendar();
}

function changeMonth(delta) {
  if (calViewMode === 'year') {
    calYear += delta;
  } else {
    calMonth += delta;
    if (calMonth > 11) { calMonth = 0; calYear++; }
    if (calMonth < 0)  { calMonth = 11; calYear--; }
  }
  renderCalendar();
}

function goToday() {
  const now = new Date();
  calYear = now.getFullYear();
  calMonth = now.getMonth();
  calViewMode = 'month';
  renderCalendar();
}

function onCalDateClick(iso) {
  const events = eventsByDate[iso] || [];
  if (events.length === 1) {
    showResourceDetail(events[0].id);
  } else if (events.length > 1) {
    showDatelistModal(iso, events);
  }
}

// ── Date-list modal ───────────────────────────────────────────────────────────
function showDatelistModal(iso, events) {
  const [y, m, d] = iso.split("-");
  const date = new Date(Number(y), Number(m)-1, Number(d));
  const fmt = date.toLocaleDateString("en-US", { weekday:"long", month:"long", day:"numeric", year:"numeric" });
  document.getElementById("datelist-title").textContent = fmt;

  document.getElementById("datelist-body").innerHTML = events.map(r => `
    <div class="date-resource-card">
      <div class="date-resource-info">
        <div class="date-resource-name">${esc(r.name)}</div>
        <div class="date-resource-meta">
          <span>${esc(r.type)}</span>
          <span>DRI: ${esc(r.dri)}</span>
          ${statusBadge(r.expiration_date)}
        </div>
      </div>
      <button class="btn-secondary btn-sm" onclick="closeDatelistModal(); showResourceDetail(${r.id})">View</button>
    </div>
  `).join("");

  document.getElementById("datelist-modal").classList.remove("hidden");
}

function closeDatelistModal() {
  document.getElementById("datelist-modal").classList.add("hidden");
}

// ── Resource detail modal ─────────────────────────────────────────────────────
function showResourceDetail(id) {
  const r = resources.find(x => x.id === id);
  if (!r) return;

  detailResourceId = id;

  document.getElementById("detail-name").textContent = r.name;
  document.getElementById("detail-type-val").textContent = r.type;
  document.getElementById("detail-dri").textContent = r.dri;
  document.getElementById("detail-expiration").innerHTML =
    `${isoToDisplay(r.expiration_date)} &nbsp; ${statusBadge(r.expiration_date)}`;

  document.getElementById("detail-purpose").innerHTML = linkify(r.purpose);
  document.getElementById("detail-instructions").innerHTML = linkify(r.generation_instructions);

  const secretWrap = document.getElementById("detail-secret-wrap");
  if (r.secret_manager_link) {
    document.getElementById("detail-secret").innerHTML =
      `<a href="${esc(r.secret_manager_link)}" target="_blank" rel="noopener">${esc(r.secret_manager_link)}</a>`;
    secretWrap.style.display = "block";
  } else {
    secretWrap.style.display = "none";
  }

  document.getElementById("detail-modal").classList.remove("hidden");
}

function closeDetailModal() {
  document.getElementById("detail-modal").classList.add("hidden");
  detailResourceId = null;
}

function editFromDetail() {
  const id = detailResourceId;
  closeDetailModal();
  openModal(id);
}

function openDeleteFromDetail() {
  const r = resources.find(x => x.id === detailResourceId);
  if (!r) return;
  closeDetailModal();
  openDeleteModal(r.id, r.name);
}

// ── Upcoming events ───────────────────────────────────────────────────────────
function renderUpcoming() {
  const container = document.getElementById("upcoming-list");
  const countEl = document.getElementById("upcoming-count");
  const today = todayISO();

  const sorted = [...resources].sort((a, b) => a.expiration_date.localeCompare(b.expiration_date));
  const expired  = sorted.filter(r => r.expiration_date < today).reverse();
  const upcoming = sorted.filter(r => r.expiration_date >= today && daysUntil(r.expiration_date) <= 30);
  const all = [...expired, ...upcoming];

  if (all.length === 0) {
    container.innerHTML = `<div class="sidebar-empty">Zarro items expiring.</div>`;
    countEl.textContent = "";
    return;
  }

  const parts = [];
  if (expired.length)  parts.push(`${expired.length} overdue`);
  if (upcoming.length) parts.push(`${upcoming.length} within 30 days`);
  countEl.textContent = parts.join(", ");

  container.innerHTML = all.map(r => {
    const days = daysUntil(r.expiration_date);
    const isOverdue = days < 0;
    let label;
    if (days < 0)        label = `<span style="color:var(--red)">Expired ${Math.abs(days)}d ago</span>`;
    else if (days === 0) label = `<span style="color:var(--red)">Today</span>`;
    else if (days <= 7)  label = `<span style="color:var(--red)">${days}d</span>`;
    else if (days <= 14) label = `<span style="color:var(--orange)">${days}d</span>`;
    else                 label = `<span style="color:var(--amber)">${days}d</span>`;

    return `
      <div class="upcoming-item${isOverdue ? ' overdue' : ''}" onclick="showResourceDetail(${r.id})">
        <div class="upcoming-item-name">${esc(r.name)}</div>
        <div class="upcoming-item-meta">
          <span>${isoToDisplay(r.expiration_date)}</span>
          ${label}
        </div>
      </div>
    `;
  }).join("");
}

// ── Resources table ───────────────────────────────────────────────────────────
function sortBy(col) {
  if (sortCol === col) sortDir *= -1;
  else { sortCol = col; sortDir = 1; }
  renderTable();
}

function renderTable() {
  const tbody = document.getElementById("resources-body");

  ["name","type","dri","expiration_date","status"].forEach(col => {
    const el = document.getElementById("sort-" + col);
    if (el) el.textContent = sortCol === col ? (sortDir === 1 ? " ▲" : " ▼") : "";
  });

  if (resources.length === 0) {
    tbody.innerHTML = `
      <tr><td colspan="6">
        <div class="empty-state">
          <strong>No resources yet</strong>
          <p>Add a resource to start tracking expiration dates.</p>
        </div>
      </td></tr>`;
    return;
  }

  const sorted = [...resources].sort((a, b) => {
    let av, bv;
    if (sortCol === "status") {
      av = daysUntil(a.expiration_date);
      bv = daysUntil(b.expiration_date);
    } else if (sortCol === "expiration_date") {
      av = a.expiration_date;
      bv = b.expiration_date;
    } else {
      av = (a[sortCol] || "").toLowerCase();
      bv = (b[sortCol] || "").toLowerCase();
    }
    if (av < bv) return -sortDir;
    if (av > bv) return  sortDir;
    return 0;
  });

  tbody.innerHTML = sorted.map(r => {
    const isOverdue = daysUntil(r.expiration_date) < 0;
    return `
    <tr${isOverdue ? ' class="overdue"' : ''}>
      <td class="name">${esc(r.name)}</td>
      <td style="color:var(--text-sec)">${esc(r.type)}</td>
      <td style="color:var(--text-sec)">${esc(r.dri)}</td>
      <td style="color:var(--text-sec)">${isoToDisplay(r.expiration_date)}</td>
      <td>${statusBadge(r.expiration_date)}</td>
      <td class="actions">
        <button class="btn-secondary btn-sm" onclick="openModal(${r.id})">Edit</button>
        <button class="btn-danger btn-sm" onclick="openDeleteModal(${r.id},'${esc(r.name)}')">Delete</button>
      </td>
    </tr>
  `;
  }).join("");
}

// ── Create / Edit modal ───────────────────────────────────────────────────────
async function openModal(id = null) {
  editingId = id;
  clearForm();

  document.getElementById("modal-title").textContent = id ? "Edit Resource" : "Add Resource";

  if (id) {
    try {
      const res = await fetch(`/api/resources/${id}`);
      const r = await res.json();
      document.getElementById("f-name").value = r.name;
      document.getElementById("f-dri").value = r.dri;
      document.getElementById("f-type").value = r.type;
      document.getElementById("f-date-picker").value = r.expiration_date;
      document.getElementById("f-purpose").value = r.purpose;
      document.getElementById("f-instructions").value = r.generation_instructions;
      document.getElementById("f-secret-link").value = r.secret_manager_link || "";
      document.getElementById("f-webhook").value = r.slack_webhook;
      onTypeChange();
    } catch (e) {
      showError("Failed to load resource details.");
    }
  }

  document.getElementById("modal").classList.remove("hidden");
  setTimeout(() => document.getElementById("f-name").focus(), 50);
}

function closeModal() {
  document.getElementById("modal").classList.add("hidden");
  editingId = null;
}

function clearForm() {
  ["f-name","f-dri","f-date-picker","f-purpose","f-instructions","f-secret-link","f-webhook"]
    .forEach(id => { document.getElementById(id).value = ""; });
  document.getElementById("f-type").value = "";
  document.getElementById("f-cert-file").value = "";
  document.getElementById("cert-status").textContent = "";
  document.getElementById("cert-status").className = "cert-status";
  document.getElementById("cert-section").style.display = "none";
  document.getElementById("webhook-test-status").textContent = "";
  document.getElementById("webhook-test-status").className = "webhook-test-status";
  hideError();
}

function onTypeChange() {
  const type = document.getElementById("f-type").value;
  document.getElementById("cert-section").style.display = type === "Certificate" ? "block" : "none";
}

// ── Webhook test ──────────────────────────────────────────────────────────────
async function testWebhook() {
  const url = document.getElementById("f-webhook").value.trim();
  const statusEl = document.getElementById("webhook-test-status");

  if (!url) {
    statusEl.textContent = "Enter a webhook URL first.";
    statusEl.className = "webhook-test-status error";
    return;
  }

  statusEl.textContent = "Sending…";
  statusEl.className = "webhook-test-status";

  try {
    const res = await fetch("/api/resources/webhook-test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ webhook_url: url }),
    });

    if (res.ok) {
      statusEl.textContent = "Test message sent successfully.";
      statusEl.className = "webhook-test-status success";
    } else {
      const err = await res.json();
      statusEl.textContent = err.detail || "Test failed.";
      statusEl.className = "webhook-test-status error";
    }
  } catch (e) {
    statusEl.textContent = "Network error.";
    statusEl.className = "webhook-test-status error";
  }
}

// ── Save resource ─────────────────────────────────────────────────────────────
async function saveResource(event) {
  event.preventDefault();
  hideError();

  const dateISO = document.getElementById("f-date-picker").value;
  if (!dateISO) { showError("Please select an expiration date."); return; }

  const certFile = document.getElementById("f-cert-file").files[0];

  const payload = {
    name:                    document.getElementById("f-name").value.trim(),
    dri:                     document.getElementById("f-dri").value.trim(),
    type:                    document.getElementById("f-type").value,
    expiration_date:         dateISO,
    purpose:                 document.getElementById("f-purpose").value.trim(),
    generation_instructions: document.getElementById("f-instructions").value.trim(),
    secret_manager_link:     document.getElementById("f-secret-link").value.trim() || null,
    slack_webhook:           document.getElementById("f-webhook").value.trim(),
  };

  const saveBtn = document.getElementById("save-btn");
  saveBtn.disabled = true;
  saveBtn.textContent = "Saving…";

  try {
    const url    = editingId ? `/api/resources/${editingId}` : "/api/resources/";
    const method = editingId ? "PUT" : "POST";
    const res    = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json();
      showError(err.detail || "Failed to save resource.");
      return;
    }

    const saved = await res.json();

    if (certFile) {
      const formData = new FormData();
      formData.append("file", certFile);
      const certRes = await fetch(`/api/resources/${saved.id}/certificate`, {
        method: "POST",
        body: formData,
      });
      if (!certRes.ok) {
        const err = await certRes.json();
        closeModal();
        await loadData();
        showToast(`Saved, but certificate upload failed: ${err.detail}`);
        return;
      }
    }

    closeModal();
    await loadData();
    showToast(editingId ? "Resource updated." : "Resource added.");
  } catch (e) {
    showError("Network error. Please try again.");
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = "Save Resource";
  }
}

// ── Certificate upload (immediate when editing) ────────────────────────────────
async function uploadCertificate() {
  const fileInput = document.getElementById("f-cert-file");
  const statusEl  = document.getElementById("cert-status");
  const file = fileInput.files[0];
  if (!file || !editingId) return;

  statusEl.textContent = "Uploading…";
  statusEl.className   = "cert-status";

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch(`/api/resources/${editingId}/certificate`, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json();
      statusEl.textContent = err.detail || "Upload failed.";
      statusEl.className   = "cert-status error";
      fileInput.value = "";
      return;
    }

    const updated = await res.json();
    document.getElementById("f-date-picker").value = updated.expiration_date;
    statusEl.textContent = `Certificate uploaded — expiry set to ${isoToDisplay(updated.expiration_date)}`;
    statusEl.className   = "cert-status success";
    await loadData();
  } catch (e) {
    statusEl.textContent = "Network error during upload.";
    statusEl.className   = "cert-status error";
    fileInput.value = "";
  }
}

// ── Delete modal ──────────────────────────────────────────────────────────────
function openDeleteModal(id, name) {
  deletingId = id;
  deletingName = name;
  document.getElementById("delete-name-display").textContent = name;
  document.getElementById("delete-confirm-input").value = "";
  document.getElementById("confirm-delete-btn").disabled = true;
  document.getElementById("delete-error").classList.remove("visible");
  document.getElementById("delete-modal").classList.remove("hidden");
  setTimeout(() => document.getElementById("delete-confirm-input").focus(), 50);
}

function closeDeleteModal() {
  document.getElementById("delete-modal").classList.add("hidden");
  deletingId = null;
  deletingName = null;
}

function onDeleteInput() {
  const val = document.getElementById("delete-confirm-input").value;
  document.getElementById("confirm-delete-btn").disabled = val !== deletingName;
}

async function confirmDelete() {
  if (!deletingId) return;

  const btn = document.getElementById("confirm-delete-btn");
  btn.disabled = true;
  btn.textContent = "Deleting…";

  try {
    const res = await fetch(`/api/resources/${deletingId}`, { method: "DELETE" });
    if (!res.ok) {
      document.getElementById("delete-error").textContent = "Failed to delete resource.";
      document.getElementById("delete-error").classList.add("visible");
      return;
    }
    closeDeleteModal();
    await loadData();
    showToast("Resource deleted. Slack notification sent.");
  } catch (e) {
    document.getElementById("delete-error").textContent = "Network error.";
    document.getElementById("delete-error").classList.add("visible");
  } finally {
    btn.disabled = false;
    btn.textContent = "Delete Resource";
  }
}

// ── UI helpers ────────────────────────────────────────────────────────────────
function showError(msg) {
  const el = document.getElementById("form-error");
  el.textContent = msg;
  el.classList.add("visible");
}

function hideError() {
  document.getElementById("form-error").classList.remove("visible");
}

let toastTimer;
function showToast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 3500);
}

function esc(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ── Modal overlay / keyboard close ────────────────────────────────────────────
["modal","detail-modal","datelist-modal","delete-modal"].forEach(id => {
  document.getElementById(id).addEventListener("click", function(e) {
    if (e.target === this) {
      closeModal(); closeDetailModal(); closeDatelistModal(); closeDeleteModal();
    }
  });
});

document.addEventListener("keydown", e => {
  if (e.key === "Escape") {
    closeModal(); closeDetailModal(); closeDatelistModal(); closeDeleteModal();
  }
});
