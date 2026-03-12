// ── Auth + user menu ──────────────────────────────────────────────────────────
let _currentUser = null;

async function loadUser() {
  try {
    const res = await fetch("/auth/me");
    if (res.status === 401) { window.location.href = "/login"; return; }
    if (!res.ok) return;
    _currentUser = await res.json();
    document.getElementById("user-label").textContent = "≡";
    document.getElementById("user-dropdown-name").textContent = _currentUser.display_name || _currentUser.email;
    document.getElementById("user-dropdown-email").textContent = _currentUser.email;
  } catch {}
}

async function signOut() {
  closeUserMenu();
  await fetch("/auth/logout", { method: "POST" }).catch(() => {});
  window.location.href = "/login";
}

function toggleUserMenu() {
  const dropdown = document.getElementById("user-dropdown");
  const btn = document.getElementById("user-avatar-btn");
  const isOpen = !dropdown.classList.contains("hidden");
  if (isOpen) {
    dropdown.classList.add("hidden");
    btn.setAttribute("aria-expanded", "false");
  } else {
    dropdown.classList.remove("hidden");
    btn.setAttribute("aria-expanded", "true");
  }
}

function closeUserMenu() {
  document.getElementById("user-dropdown").classList.add("hidden");
  document.getElementById("user-avatar-btn").setAttribute("aria-expanded", "false");
}

// Close dropdown when clicking outside
document.addEventListener("click", e => {
  const menu = document.getElementById("user-menu");
  if (menu && !menu.contains(e.target)) closeUserMenu();
});

// Intercept 401 responses from API calls and redirect to login.
const _origFetch = window.fetch;
window.fetch = async function(...args) {
  const res = await _origFetch(...args);
  if (res.status === 401) {
    const url = typeof args[0] === "string" ? args[0] : args[0]?.url ?? "";
    // Only redirect for app API calls, not for the auth endpoints themselves.
    if (!url.startsWith("/auth/")) {
      window.location.href = "/login";
    }
  }
  return res;
};

// ── API Keys (personal modal) ─────────────────────────────────────────────────

function openApiKeysModal() {
  closeUserMenu();
  document.getElementById("api-key-reveal").classList.add("hidden");
  document.getElementById("api-key-name").value = "";
  document.getElementById("api-keys-modal").classList.remove("hidden");
  loadApiKeys();
}

function closeApiKeysModal() {
  document.getElementById("api-keys-modal").classList.add("hidden");
  document.getElementById("api-key-reveal").classList.add("hidden");
}

async function loadApiKeys() {
  const res = await fetch("/api/keys/");
  if (!res.ok) return;
  const keys = await res.json();
  const list = document.getElementById("api-keys-list");
  if (keys.length === 0) {
    list.innerHTML = '<p style="color:var(--muted);font-size:0.85rem">No active API keys.</p>';
    return;
  }
  list.innerHTML = `
    <table class="admin-table" style="margin-bottom:0">
      <thead><tr><th>Name</th><th>Prefix</th><th>Last used</th><th></th></tr></thead>
      <tbody>
        ${keys.map(k => `
          <tr>
            <td>${esc(k.name)}</td>
            <td><code style="font-size:0.8rem">${esc(k.key_prefix)}</code></td>
            <td style="color:var(--muted);font-size:0.8rem">${k.last_used_at ? new Date(k.last_used_at).toLocaleDateString() : "Never"}</td>
            <td><button class="btn-danger btn-sm" onclick="revokeApiKey(${k.id})">Revoke</button></td>
          </tr>`).join("")}
      </tbody>
    </table>`;
}

async function createApiKey() {
  const name = document.getElementById("api-key-name").value.trim();
  if (!name) { showToast("Enter a name for the key."); return; }
  const res = await fetch("/api/keys/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) { showToast("Failed to create key."); return; }
  const data = await res.json();
  document.getElementById("api-key-name").value = "";
  document.getElementById("api-key-value").textContent = data.full_key;
  document.getElementById("api-key-reveal").classList.remove("hidden");
  loadApiKeys();
}

async function revokeApiKey(id) {
  if (!confirm("Revoke this API key? Any integrations using it will stop working.")) return;
  const res = await fetch(`/api/keys/${id}`, { method: "DELETE" });
  if (!res.ok) { showToast("Failed to revoke key."); return; }
  document.getElementById("api-key-reveal").classList.add("hidden");
  loadApiKeys();
}

function copyApiKey() {
  const val = document.getElementById("api-key-value").textContent;
  navigator.clipboard.writeText(val).then(() => showToast("Copied to clipboard."));
}

// ── API Keys (admin view on Admin tab) ────────────────────────────────────────

async function loadAdminApiKeys() {
  const tbody = document.getElementById("admin-all-keys-body");
  if (!tbody) return;
  tbody.innerHTML = `<tr><td colspan="5" class="loading">Loading…</td></tr>`;
  const res = await fetch("/admin/api-keys");
  if (!res.ok) { tbody.innerHTML = `<tr><td colspan="5" class="loading">Failed to load.</td></tr>`; return; }
  const keys = await res.json();
  if (!keys.length) {
    tbody.innerHTML = `<tr><td colspan="5" class="loading">No active API keys.</td></tr>`;
    return;
  }
  tbody.innerHTML = keys.map(k => `
    <tr>
      <td>${esc(k.name)}</td>
      <td style="color:var(--muted);font-size:0.8rem">${esc(k.user_email)}</td>
      <td><code style="font-size:0.8rem">${esc(k.key_prefix)}</code></td>
      <td style="color:var(--muted);font-size:0.8rem">${k.last_used_at ? new Date(k.last_used_at).toLocaleDateString() : "Never"}</td>
      <td><button class="btn-danger btn-sm" onclick="revokeAdminApiKey(${k.id})">Revoke</button></td>
    </tr>`).join("");
}

async function revokeAdminApiKey(id) {
  if (!confirm("Revoke this API key? Any integrations using it will stop working.")) return;
  const res = await fetch(`/admin/api-keys/${id}`, { method: "DELETE" });
  if (!res.ok) { showToast("Failed to revoke key."); return; }
  loadAdminApiKeys();
}

// ── State ─────────────────────────────────────────────────────────────────────
let resources = [];
let _teams = [];   // [{id, name}] — loaded once on loadData and on modal open
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
(async function init() {
  const now = new Date();
  calYear = now.getFullYear();
  calMonth = now.getMonth();
  await loadUser();
  await loadData();
  _checkTeamSetup();
  const hash = window.location.hash.slice(1);
  if (hash && ["overview", "resources", "admin", "docs"].includes(hash)) {
    switchTab(hash);
  }
})();

async function loadData() {
  try {
    const [resRes, teamRes] = await Promise.all([
      fetch("/api/resources/"),
      fetch("/api/resources/teams"),
    ]);
    resources = resRes.ok ? await resRes.json() : [];
    _teams = teamRes.ok ? await teamRes.json() : [];
  } catch (e) {
    resources = [];
    _teams = [];
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
  if (name === "admin") loadAdminTab();
  history.replaceState(null, "", "#" + name);
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

function goToCurrentMonth() {
  const now = new Date();
  calYear = now.getFullYear();
  calMonth = now.getMonth();
  calViewMode = 'month';
  document.getElementById("cal-view-toggle").textContent = "Year View";
  renderCalendar();
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
      document.getElementById("f-cert-endpoint").value = r.certificate_url || "";
      document.getElementById("f-auto-refresh").checked = r.auto_refresh_expiry || false;
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
  document.getElementById("f-cert-endpoint").value = "";
  document.getElementById("f-auto-refresh").checked = false;
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

  const isCert = document.getElementById("f-type").value === "Certificate";
  const payload = {
    name:                    document.getElementById("f-name").value.trim(),
    dri:                     document.getElementById("f-dri").value.trim(),
    type:                    document.getElementById("f-type").value,
    expiration_date:         dateISO,
    purpose:                 document.getElementById("f-purpose").value.trim(),
    generation_instructions: document.getElementById("f-instructions").value.trim(),
    secret_manager_link:     document.getElementById("f-secret-link").value.trim() || null,
    slack_webhook:           document.getElementById("f-webhook").value.trim(),
    certificate_url:         isCert ? (document.getElementById("f-cert-endpoint").value.trim() || null) : null,
    auto_refresh_expiry:     isCert && document.getElementById("f-auto-refresh").checked,
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

    const wasEditing = !!editingId;
    closeModal();
    await loadData();
    showToast(wasEditing ? "Resource updated." : "Resource added.");
    if (!wasEditing) switchTab("resources");
  } catch (e) {
    showError("Network error. Please try again.");
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = "Save Resource";
  }
}

// ── Certificate expiry lookup ──────────────────────────────────────────────────
async function lookupCertExpiry() {
  const endpoint = document.getElementById("f-cert-endpoint").value.trim();
  const statusEl = document.getElementById("cert-status");

  if (!endpoint) {
    statusEl.textContent = "Enter an endpoint URL or hostname first.";
    statusEl.className = "cert-status error";
    return;
  }

  statusEl.textContent = "Connecting…";
  statusEl.className = "cert-status";

  try {
    const res = await fetch("/api/resources/cert-lookup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ endpoint }),
    });

    if (!res.ok) {
      const err = await res.json();
      statusEl.textContent = err.detail || "Failed to retrieve certificate.";
      statusEl.className = "cert-status error";
      return;
    }

    const data = await res.json();
    document.getElementById("f-date-picker").value = data.expiration_date;
    statusEl.textContent = `Expiry detected: ${isoToDisplay(data.expiration_date)}`;
    statusEl.className = "cert-status success";
  } catch (e) {
    statusEl.textContent = "Network error. Please try again.";
    statusEl.className = "cert-status error";
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
["modal","detail-modal","datelist-modal","delete-modal","api-keys-modal"].forEach(id => {
  document.getElementById(id).addEventListener("click", function(e) {
    if (e.target === this) {
      closeModal(); closeDetailModal(); closeDatelistModal(); closeDeleteModal(); closeApiKeysModal();
    }
  });
});

document.addEventListener("keydown", e => {
  if (e.key === "Escape") {
    closeModal(); closeDetailModal(); closeDatelistModal(); closeDeleteModal();
    closeApiKeysModal();
    closeUserMenu();
  }
});

// ── Admin tab ─────────────────────────────────────────────────────────────────

function loadAdminTab() {
  if (!_currentUser) return;
  if (!_currentUser.is_admin) {
    document.getElementById("admin-no-access").style.display = "";
    document.getElementById("admin-content").style.display = "none";
    return;
  }
  document.getElementById("admin-no-access").style.display = "none";
  document.getElementById("admin-content").style.display = "";
  loadAdminSettings();
  loadAdminUsers();
  loadAdminTeams();  // populates the team rename field
  loadAdminApiKeys();
  loadDeletedResources();
  loadAuditLog();
}

// ── Notification settings ─────────────────────────────────────────────────────
async function loadAdminSettings() {
  const msgEl = document.getElementById("adm-settings-msg");
  if (msgEl) { msgEl.textContent = ""; msgEl.className = "admin-msg"; }
  const hourSel = document.getElementById("adm-notify-hour");
  if (!hourSel.options.length) {
    for (let h = 0; h < 24; h++) {
      const opt = document.createElement("option");
      opt.value = h;
      const suffix = h < 12 ? "AM" : "PM";
      const display = h === 0 ? "12:00 AM" : h < 12 ? `${h}:00 AM` : h === 12 ? "12:00 PM" : `${h - 12}:00 PM`;
      opt.textContent = display;
      hourSel.appendChild(opt);
    }
  }
  try {
    const res = await fetch("/admin/settings");
    if (!res.ok) return;
    const s = await res.json();
    document.querySelectorAll("#adm-reminder-days input[type=checkbox]").forEach(cb => {
      cb.checked = s.reminder_days.includes(parseInt(cb.value, 10));
    });
    hourSel.value = s.notify_hour;
    document.getElementById("adm-slack-webhook").value = s.slack_webhook || "";
    document.getElementById("adm-alert-on-overdue").checked = s.alert_on_overdue || false;
    document.getElementById("adm-alert-on-delete").checked = s.alert_on_delete || false;
  } catch {}
}

async function testAdminWebhook() {
  const url = document.getElementById("adm-slack-webhook").value.trim();
  const statusEl = document.getElementById("admin-webhook-test-status");
  if (!url) {
    statusEl.textContent = "Enter a webhook URL first.";
    statusEl.className = "webhook-test-status error";
    return;
  }
  statusEl.textContent = "Sending…";
  statusEl.className = "webhook-test-status";
  try {
    const res = await fetch("/admin/webhook-test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ webhook_url: url }),
    });
    if (res.ok) {
      statusEl.textContent = "Test message sent successfully.";
      statusEl.className = "webhook-test-status success";
    } else {
      const err = await res.json().catch(() => ({}));
      statusEl.textContent = err.detail || "Test failed.";
      statusEl.className = "webhook-test-status error";
    }
  } catch {
    statusEl.textContent = "Network error.";
    statusEl.className = "webhook-test-status error";
  }
}

async function saveAdminSettings() {
  const msgEl = document.getElementById("adm-settings-msg");
  msgEl.textContent = "";
  msgEl.className = "admin-msg";

  const days = Array.from(document.querySelectorAll("#adm-reminder-days input[type=checkbox]:checked"))
    .map(cb => parseInt(cb.value, 10));
  const hour = parseInt(document.getElementById("adm-notify-hour").value, 10);
  const slackWebhook = document.getElementById("adm-slack-webhook").value.trim() || null;
  const alertOnOverdue = document.getElementById("adm-alert-on-overdue").checked;
  const alertOnDelete = document.getElementById("adm-alert-on-delete").checked;

  if (!days.length) {
    msgEl.textContent = "Select at least one reminder day.";
    msgEl.className = "admin-msg error";
    return;
  }

  try {
    const res = await fetch("/admin/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reminder_days: days, notify_hour: hour, slack_webhook: slackWebhook, alert_on_overdue: alertOnOverdue, alert_on_delete: alertOnDelete }),
    });
    if (res.ok) {
      msgEl.textContent = "Settings saved.";
      msgEl.className = "admin-msg success";
    } else {
      const err = await res.json().catch(() => ({}));
      msgEl.textContent = err.detail || "Failed to save settings.";
      msgEl.className = "admin-msg error";
    }
  } catch {
    msgEl.textContent = "Network error.";
    msgEl.className = "admin-msg error";
  }
}

// ── Team (singleton) ──────────────────────────────────────────────────────────
async function loadAdminTeams() {
  // Populate the rename field in the Admin > Team card
  if (!_teams.length) {
    try {
      const res = await fetch("/admin/teams");
      if (res.ok) _teams = await res.json();
    } catch {}
  }
  const input = document.getElementById("adm-team-name");
  if (input && _teams.length) input.value = _teams[0].name;
}

async function saveTeamName() {
  const input = document.getElementById("adm-team-name");
  const msgEl = document.getElementById("adm-team-msg");
  const name = input.value.trim();
  msgEl.textContent = "";
  msgEl.className = "admin-msg";
  if (!name) { msgEl.textContent = "Team name cannot be empty."; msgEl.className = "admin-msg error"; return; }

  if (_teams.length) {
    // Rename existing team
    const res = await fetch(`/admin/teams/${_teams[0].id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    if (res.ok) {
      _teams[0].name = name;
      msgEl.textContent = "Team name updated.";
      msgEl.className = "admin-msg success";
    } else {
      const err = await res.json().catch(() => ({}));
      msgEl.textContent = err.detail || "Failed to update.";
      msgEl.className = "admin-msg error";
    }
  } else {
    // Create (shouldn't normally be reached from Admin since setup modal handles this)
    const res = await fetch("/admin/teams", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    if (res.ok) {
      _teams = [await res.json()];
      msgEl.textContent = "Team created.";
      msgEl.className = "admin-msg success";
    } else {
      const err = await res.json().catch(() => ({}));
      msgEl.textContent = err.detail || "Failed to create team.";
      msgEl.className = "admin-msg error";
    }
  }
}

// ── Team setup modal (shown on first login when no team exists) ────────────────
function _checkTeamSetup() {
  if (!_currentUser || !_currentUser.is_admin) return;
  if (_teams.length === 0) {
    document.getElementById("team-setup-modal").classList.remove("hidden");
    setTimeout(() => document.getElementById("setup-team-name").focus(), 100);
  }
}

async function submitTeamSetup() {
  const input = document.getElementById("setup-team-name");
  const errEl = document.getElementById("setup-team-error");
  const name = input.value.trim();
  errEl.textContent = "";
  if (!name) { errEl.textContent = "Please enter a team name."; return; }

  const res = await fetch("/admin/teams", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (res.ok) {
    _teams = [await res.json()];
    document.getElementById("team-setup-modal").classList.add("hidden");
    showToast(`Team "${name}" created. Welcome to Tribal!`);
  } else {
    const err = await res.json().catch(() => ({}));
    errEl.textContent = err.detail || "Failed to create team.";
  }
}

// ── Users ─────────────────────────────────────────────────────────────────────
async function loadAdminUsers() {
  const tbody = document.getElementById("admin-users-body");
  tbody.innerHTML = `<tr><td colspan="4" class="loading">Loading…</td></tr>`;
  try {
    const res = await fetch("/admin/users");
    if (!res.ok) { tbody.innerHTML = `<tr><td colspan="4" class="loading">Failed to load users.</td></tr>`; return; }
    const users = await res.json();
    if (!users.length) {
      tbody.innerHTML = `<tr><td colspan="4" class="loading">No users found.</td></tr>`;
      return;
    }
    tbody.innerHTML = users.map(u => `
      <tr>
        <td>${esc(u.display_name || "—")}</td>
        <td>${esc(u.email)}</td>
        <td>
          ${u.is_admin ? '<span class="badge-admin">Admin</span>' : '<span class="badge-member">Member</span>'}
          ${u.is_account_creator ? '<span class="badge-creator" title="Account creator — admin rights and account are permanent">Creator</span>' : ''}
        </td>
        <td class="actions" style="gap:6px">
          ${u.id === _currentUser.id
            ? '<span style="color:var(--text-mut);font-size:12px">You</span>'
            : u.is_account_creator
              ? '<span style="color:var(--text-mut);font-size:12px">Protected</span>'
              : `<button class="btn-secondary btn-sm" onclick="toggleUserAdmin(${u.id}, ${u.is_admin})">${u.is_admin ? "Remove Admin" : "Make Admin"}</button>
            <button class="btn-danger btn-sm" onclick="deleteAdminUser(${u.id}, '${esc(u.email)}')">Delete</button>`}
        </td>
      </tr>
    `).join("");
  } catch {
    tbody.innerHTML = `<tr><td colspan="4" class="loading">Network error.</td></tr>`;
  }
}

async function toggleUserAdmin(userId, currentIsAdmin) {
  const res = await fetch(`/admin/users/${userId}/role?is_admin=${!currentIsAdmin}`, { method: "PUT" });
  if (res.ok) {
    showToast(currentIsAdmin ? "Admin access removed." : "User promoted to admin.");
    loadAdminUsers();
  } else {
    const err = await res.json().catch(() => ({}));
    showToast(err.detail || "Failed to update role.");
  }
}

async function deleteAdminUser(userId, email) {
  if (!confirm(`Delete user "${email}"? This cannot be undone.`)) return;
  const res = await fetch(`/admin/users/${userId}`, { method: "DELETE" });
  if (res.ok) {
    showToast("User deleted.");
    loadAdminUsers();
  } else {
    const err = await res.json().catch(() => ({}));
    showToast(err.detail || "Failed to delete user.");
  }
}

// ── Deleted resources ─────────────────────────────────────────────────────────

async function loadDeletedResources() {
  const tbody = document.getElementById("admin-deleted-body");
  if (!tbody) return;
  tbody.innerHTML = `<tr><td colspan="5" class="loading">Loading…</td></tr>`;
  try {
    const res = await fetch("/admin/resources/deleted");
    if (!res.ok) { tbody.innerHTML = `<tr><td colspan="5" class="loading">Failed to load.</td></tr>`; return; }
    const items = await res.json();
    if (!items.length) {
      tbody.innerHTML = `<tr><td colspan="5" class="loading">No deleted resources.</td></tr>`;
      return;
    }
    tbody.innerHTML = items.map(r => `
      <tr>
        <td>${esc(r.name)}</td>
        <td style="color:var(--text-sec)">${esc(r.type)}</td>
        <td style="color:var(--text-sec)">${esc(r.dri)}</td>
        <td style="color:var(--text-sec);font-size:0.8rem">${new Date(r.deleted_at + "Z").toLocaleDateString()}</td>
        <td><button class="btn-secondary btn-sm" onclick="restoreResource(${r.id})">Restore</button></td>
      </tr>`).join("");
  } catch {
    tbody.innerHTML = `<tr><td colspan="5" class="loading">Network error.</td></tr>`;
  }
}

async function restoreResource(id) {
  const res = await fetch(`/admin/resources/${id}/restore`, { method: "POST" });
  if (res.ok) {
    showToast("Resource restored.");
    loadDeletedResources();
    await loadData();
  } else {
    const err = await res.json().catch(() => ({}));
    showToast(err.detail || "Failed to restore resource.");
  }
}

// ── Audit log ─────────────────────────────────────────────────────────────────
const _ACTION_LABELS = {
  "resource.create": "Created",
  "resource.update": "Updated",
  "resource.delete": "Deleted",
  "resource.cert_upload": "Cert Uploaded",
  "user.create": "User Registered",
  "user.delete": "User Deleted",
  "user.login": "Logged In",
  "api_key.create": "API Key Created",
  "api_key.delete": "API Key Revoked",
};

async function loadAuditLog() {
  const tbody = document.getElementById("admin-audit-body");
  tbody.innerHTML = `<tr><td colspan="4" class="loading">Loading…</td></tr>`;
  try {
    const res = await fetch("/admin/audit-log?limit=25");
    if (!res.ok) { tbody.innerHTML = `<tr><td colspan="4" class="loading">Failed to load audit log.</td></tr>`; return; }
    const entries = await res.json();
    if (!entries.length) {
      tbody.innerHTML = `<tr><td colspan="4" class="loading">No audit entries yet. Actions on resources will appear here.</td></tr>`;
      return;
    }
    tbody.innerHTML = entries.map(e => {
      const dt = new Date(e.created_at + "Z");
      const fmt = dt.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
        + " " + dt.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
      const action = _ACTION_LABELS[e.action] || e.action;
      return `<tr>
        <td style="white-space:nowrap;color:var(--text-sec)">${esc(fmt)}</td>
        <td style="color:var(--text-sec)">${esc(e.user_email || "system")}</td>
        <td>${esc(action)}</td>
        <td>${esc(e.resource_name || "—")}</td>
      </tr>`;
    }).join("");
  } catch {
    tbody.innerHTML = `<tr><td colspan="4" class="loading">Network error.</td></tr>`;
  }
}
