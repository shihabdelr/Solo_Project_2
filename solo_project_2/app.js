/*https://soloproj.netlify.app/*/

const API_BASE = "https://solo-project-2-7rmr.onrender.com/api";

let totalCount = 0;
let totalPages = 1;

let statsTotalCount = 0;
let statsTeamsPerLeague = {};

let teams = [];
let currentPage = 1;

let editingId = null;

// ===== Step 1: Page size + cookie persistence =====
const PAGE_SIZE_COOKIE = "pageSize";
const ALLOWED_PAGE_SIZES = [5, 10, 20, 50];

function getCookie(name) {
  const cookies = document.cookie ? document.cookie.split("; ") : [];
  for (let i = 0; i < cookies.length; i++) {
    const [k, ...rest] = cookies[i].split("=");
    if (k === name) return decodeURIComponent(rest.join("="));
  }
  return null;
}

function setCookie(name, value, days = 90) {
  const expires = new Date(Date.now() + days * 864e5).toUTCString();
  document.cookie = `${name}=${encodeURIComponent(String(value))}; Expires=${expires}; Path=/; SameSite=Lax`;
}

function normalizePageSize(raw) {
  const n = Number(raw);
  if (!Number.isFinite(n)) return 10;
  return ALLOWED_PAGE_SIZES.includes(n) ? n : 10;
}

let pageSize = normalizePageSize(getCookie(PAGE_SIZE_COOKIE) ?? 10);
setCookie(PAGE_SIZE_COOKIE, pageSize);

// ===== Step 4: Search / Filter / Sort state =====
let searchQuery = "";
let leagueFilter = "";
let sortField = "name";
let sortDir = "asc";
let leaguesCache = [];

// ===== Step 3: Image fallback =====
const FALLBACK_IMG = "https://placehold.co/80x80?text=No+Image";

function safeImg(url, name) {
  if (url && String(url).trim()) return String(url).trim();
  const label = encodeURIComponent((name || "Team").slice(0, 12));
  return `https://placehold.co/80x80?text=${label}`;
}

function escapeHtml(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function loadTeams(page = 1) {
  const params = new URLSearchParams();
  params.set("page", String(page));
  params.set("pageSize", String(pageSize));

  if (searchQuery.trim()) params.set("q", searchQuery.trim());
  if (leagueFilter) params.set("league", leagueFilter);

  params.set("sort", sortField);
  params.set("dir", sortDir);

  const res = await fetch(`${API_BASE}/teams?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load teams (HTTP ${res.status})`);

  const data = await res.json();

  teams = data.items;
  currentPage = data.page;

  totalCount = data.totalCount;
  totalPages = Math.max(1, Math.ceil(totalCount / pageSize));

  renderList();
}

async function loadStats() {
  const res = await fetch(`${API_BASE}/stats`);
  if (!res.ok) throw new Error(`Failed to load stats (HTTP ${res.status})`);

  const data = await res.json();
  statsTotalCount = data.totalCount;
  statsTeamsPerLeague = data.teamsPerLeague || {};

  // Populate league dropdown options
  leaguesCache = Object.keys(statsTeamsPerLeague).sort((a, b) => a.localeCompare(b));

  renderStats();
}

function show(view) {
  const listView = document.getElementById("listView");
  const formView = document.getElementById("formView");
  const statsView = document.getElementById("statsView");

  listView.style.display = "none";
  formView.style.display = "none";
  statsView.style.display = "none";

  if (view === "list") listView.style.display = "block";
  if (view === "form") formView.style.display = "block";
  if (view === "stats") statsView.style.display = "block";
}

function renderList() {
  const list = document.getElementById("listView");

  const startNum = totalCount === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const endNum = Math.min(currentPage * pageSize, totalCount);

  const prevDisabled = currentPage <= 1 ? "disabled" : "";
  const nextDisabled = currentPage >= totalPages ? "disabled" : "";

  const pageSizeOptions = ALLOWED_PAGE_SIZES.map(
    (s) => `<option value="${s}" ${s === pageSize ? "selected" : ""}>${s}</option>`
  ).join("");

  const leagueOptions = [
    `<option value="">All leagues</option>`,
    ...leaguesCache.map(l => `<option value="${escapeHtml(l)}" ${l === leagueFilter ? "selected" : ""}>${escapeHtml(l)}</option>`)
  ].join("");

  const sortOptions = [
    ["name", "Name"],
    ["founded", "Founded"],
    ["league", "League"],
    ["country", "Country"]
  ].map(([v, label]) => `<option value="${v}" ${v === sortField ? "selected" : ""}>${label}</option>`).join("");

  let html = `
    <h2>Teams</h2>

    <div class="toolbar">
      <button id="prevPage" ${prevDisabled}>Previous</button>
      <div><b>Page ${currentPage}</b> of ${totalPages}</div>
      <button id="nextPage" ${nextDisabled}>Next</button>

      <label class="toolbar-item">
        Page size:
        <select id="pageSizeSelect">
          ${pageSizeOptions}
        </select>
      </label>

      <label class="toolbar-item">
        Search:
        <input id="searchInput" type="text" placeholder="e.g., Real" value="${escapeHtml(searchQuery)}" />
      </label>

      <label class="toolbar-item">
        League:
        <select id="leagueSelect">
          ${leagueOptions}
        </select>
      </label>

      <label class="toolbar-item">
        Sort:
        <select id="sortSelect">
          ${sortOptions}
        </select>
      </label>

      <label class="toolbar-item">
        Dir:
        <select id="dirSelect">
          <option value="asc" ${sortDir === "asc" ? "selected" : ""}>Asc</option>
          <option value="desc" ${sortDir === "desc" ? "selected" : ""}>Desc</option>
        </select>
      </label>

      <button id="applyFilters" class="toolbar-item">Apply</button>
      <button id="clearFilters" class="toolbar-item">Clear</button>

      <div class="toolbar-spacer"></div>
      <div>Showing ${startNum}–${endNum} of ${totalCount}</div>
    </div>
  `;

  if (!teams.length) {
    html += `<p class="empty-state">No results found. Try changing your search/filter.</p>`;
    list.innerHTML = html;
    wireToolbarHandlers();
    return;
  }

  html += `
    <table border="1" cellpadding="6">
      <tr>
        <th>Image</th>
        <th>Name</th>
        <th>League</th>
        <th>Country</th>
        <th>Founded</th>
        <th>Stadium</th>
        <th>Edits</th>
      </tr>
  `;

  for (let i = 0; i < teams.length; i++) {
    const t = teams[i];
    html += `
      <tr>
        <td>
          <img class="team-thumb"
               src="${safeImg(t.imageUrl, t.name)}"
               alt="${escapeHtml(t.name)} logo"
               onerror="this.onerror=null; this.src='${FALLBACK_IMG}';" />
        </td>
        <td>${escapeHtml(t.name)}</td>
        <td>${escapeHtml(t.league)}</td>
        <td>${escapeHtml(t.country)}</td>
        <td>${escapeHtml(t.founded)}</td>
        <td>${escapeHtml(t.stadium || "")}</td>
        <td>
          <button onclick="editTeam('${escapeHtml(t.id)}')">Edit</button>
          <button onclick="deleteTeam('${escapeHtml(t.id)}')">Delete</button>
        </td>
      </tr>
    `;
  }

  html += `</table>`;
  list.innerHTML = html;

  wireToolbarHandlers();
}

function wireToolbarHandlers() {
  document.getElementById("prevPage")?.addEventListener("click", () => {
    if (currentPage > 1) loadTeams(currentPage - 1);
  });

  document.getElementById("nextPage")?.addEventListener("click", () => {
    if (currentPage < totalPages) loadTeams(currentPage + 1);
  });

  document.getElementById("pageSizeSelect")?.addEventListener("change", async (e) => {
    pageSize = normalizePageSize(e.target.value);
    setCookie(PAGE_SIZE_COOKIE, pageSize);
    await loadTeams(1);
  });

  document.getElementById("applyFilters")?.addEventListener("click", async () => {
    searchQuery = document.getElementById("searchInput").value;
    leagueFilter = document.getElementById("leagueSelect").value;
    sortField = document.getElementById("sortSelect").value;
    sortDir = document.getElementById("dirSelect").value;
    await loadTeams(1);
  });

  document.getElementById("clearFilters")?.addEventListener("click", async () => {
    searchQuery = "";
    leagueFilter = "";
    sortField = "name";
    sortDir = "asc";
    await loadTeams(1);
  });

  // Optional: press Enter in search box to apply
  document.getElementById("searchInput")?.addEventListener("keydown", async (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      document.getElementById("applyFilters")?.click();
    }
  });
}

function renderStats() {
  const stats = document.getElementById("statsView");

  let list = "<ul>";
  for (const league in statsTeamsPerLeague) {
    list += `<li>${escapeHtml(league)}: ${escapeHtml(statsTeamsPerLeague[league])}</li>`;
  }
  list += "</ul>";

  stats.innerHTML = `
    <h2>Stats</h2>
    <p><b>Total teams (entire dataset):</b> ${escapeHtml(statsTotalCount)}</p>
    <p><b>Current page size:</b> ${escapeHtml(pageSize)}</p>
    <p><b>Teams per league (entire dataset):</b></p>
    ${list}
  `;
}

function fillForm(team) {
  const nameInput = document.getElementById("name");
  const leagueInput = document.getElementById("league");
  const countryInput = document.getElementById("country");
  const foundedInput = document.getElementById("founded");
  const stadiumInput = document.getElementById("stadium");
  const imageUrlInput = document.getElementById("imageUrl");

  if (team !== null) {
    nameInput.value = team.name;
    leagueInput.value = team.league;
    countryInput.value = team.country;
    foundedInput.value = team.founded;
    stadiumInput.value = team.stadium;
    imageUrlInput.value = team.imageUrl || "";
  } else {
    nameInput.value = "";
    leagueInput.value = "";
    countryInput.value = "";
    foundedInput.value = "";
    stadiumInput.value = "";
    imageUrlInput.value = "";
  }
}

function startAdd() {
  editingId = null;
  clearFormErrors();
  fillForm(null);

  document.querySelector("#formView h2").textContent = "Add Team";
  document.getElementById("submitBtn").textContent = "Add Team";

  show("form");
}

window.editTeam = function (id) {
  const team = teams.find(t => String(t.id) === String(id));
  if (!team) {
    alert("Could not find that team on this page. Try reloading.");
    return;
  }

  editingId = id;
  clearFormErrors();
  fillForm(team);

  document.querySelector("#formView h2").textContent = "Edit Team";
  document.getElementById("submitBtn").textContent = "Save Changes";

  show("form");
};

window.deleteTeam = async function (id) {
  const ok = confirm("Delete this team? This cannot be undone.");
  if (!ok) return;

  try {
    const res = await fetch(`${API_BASE}/teams/${id}`, { method: "DELETE" });

    if (res.status === 404) {
      alert("That record no longer exists. Reloading...");
      await loadTeams(currentPage);
      return;
    }

    if (!res.ok) {
      throw new Error(`DELETE failed (HTTP ${res.status})`);
    }

    const newTotal = totalCount - 1;
    const newTotalPages = Math.max(1, Math.ceil(newTotal / pageSize));
    const targetPage = Math.min(currentPage, newTotalPages);

    await loadTeams(targetPage);
  } catch (err) {
    console.error(err);
    alert("Could not delete team. Is the backend running?");
  }
};

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("showList").addEventListener("click", () => show("list"));
  document.getElementById("showForm").addEventListener("click", startAdd);
  document.getElementById("showStats").addEventListener("click", () => {
    show("stats");
    loadStats().catch((err) => {
      console.error(err);
      alert("Could not load stats from backend. Make sure Flask is running.");
    });
  });

  document.getElementById("cancel").addEventListener("click", () => show("list"));

  document.getElementById("teamForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    clearFormErrors();

    const teamData = {
      name: document.getElementById("name").value,
      league: document.getElementById("league").value,
      country: document.getElementById("country").value,
      founded: document.getElementById("founded").value,
      stadium: document.getElementById("stadium").value,
      imageUrl: document.getElementById("imageUrl").value
    };

    const url = editingId
      ? `${API_BASE}/teams/${editingId}`
      : `${API_BASE}/teams`;

    const method = editingId ? "PUT" : "POST";

    try {
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(teamData)
      });

      if (res.status === 400) {
        const data = await res.json();
        showFormErrors(data.errors || { form: "Validation failed." });
        return;
      }

      if (res.status === 404) {
        showFormErrors({ form: "That record no longer exists (404). Refresh and try again." });
        return;
      }

      if (!res.ok) {
        throw new Error(`${method} failed (HTTP ${res.status})`);
      }

      show("list");

      if (method === "POST") {
        const newTotal = totalCount + 1;
        const newTotalPages = Math.max(1, Math.ceil(newTotal / pageSize));
        await loadTeams(newTotalPages);
      } else {
        await loadTeams(currentPage);
      }

      editingId = null;
    } catch (err) {
      console.error(err);
      showFormErrors({ form: "Could not save team. Is the backend running?" });
    }
  });

  // Preload stats in background so league dropdown is populated
  loadStats().catch(() => {});

  show("list");
  loadTeams(1).catch((err) => {
    console.error(err);
    alert("Could not load teams from backend. Make sure Flask is running.");
  });
});

function clearFormErrors() {
  const box = document.getElementById("formErrors");
  if (!box) return;
  box.style.display = "none";
  box.innerHTML = "";
}

function showFormErrors(errors) {
  const box = document.getElementById("formErrors");
  if (!box) return;

  let html = "<ul>";
  for (const field in errors) {
    html += `<li><b>${escapeHtml(field)}:</b> ${escapeHtml(errors[field])}</li>`;
  }
  html += "</ul>";

  box.innerHTML = html;
  box.style.display = "block";
}