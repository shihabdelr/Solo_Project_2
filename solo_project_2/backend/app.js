/*https://soloproj.netlify.app/*/

// Use Render API when running locally, but relative /api when served by Flask on Render
const API_BASE =
  (location.hostname === "localhost" || location.hostname === "127.0.0.1")
    ? "https://solo-project-2-7rmr.onrender.com/api"
    : "/api";

let totalCount = 0;
let totalPages = 1;

let statsTotalCount = 0;
let statsTeamsPerLeague = {};

let currentPage = 1;
let pageSize = 10;

let currentSort = "name";
let currentDir = "asc";

let currentQuery = "";
let currentLeague = "";

let editingId = null;

function escapeHtml(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function safeImg(url, teamName) {
  // backend always sends a valid URL now (placeholder or /static/uploads/..)
  if (!url) return `https://placehold.co/80x80?text=${encodeURIComponent((teamName || "Team").slice(0, 12))}`;
  return url;
}

function show(view) {
  document.getElementById("listView").style.display = view === "list" ? "block" : "none";
  document.getElementById("formView").style.display = view === "form" ? "block" : "none";
  document.getElementById("statsView").style.display = view === "stats" ? "block" : "none";
}

function clearFormErrors() {
  const el = document.getElementById("formErrors");
  el.style.display = "none";
  el.innerHTML = "";
}

function showFormErrors(errors) {
  const el = document.getElementById("formErrors");
  el.style.display = "block";

  const entries = Object.entries(errors || {});
  if (entries.length === 0) {
    el.innerHTML = "<p>Something went wrong.</p>";
    return;
  }

  el.innerHTML = entries
    .map(([k, v]) => `<p><strong>${escapeHtml(k)}:</strong> ${escapeHtml(v)}</p>`)
    .join("");
}

function clearForm() {
  editingId = null;
  document.getElementById("submitBtn").textContent = "Add Team";

  document.getElementById("name").value = "";
  document.getElementById("league").value = "";
  document.getElementById("country").value = "";
  document.getElementById("founded").value = "";
  document.getElementById("stadium").value = "";
  document.getElementById("imageFile").value = ""; // clear file chooser

  clearFormErrors();
}

function fillForm(team) {
  editingId = team.id;
  document.getElementById("submitBtn").textContent = "Edit Team";

  document.getElementById("name").value = team.name || "";
  document.getElementById("league").value = team.league || "";
  document.getElementById("country").value = team.country || "";
  document.getElementById("founded").value = team.founded || "";
  document.getElementById("stadium").value = team.stadium || "";
  document.getElementById("imageFile").value = ""; // user can optionally choose new file
  clearFormErrors();
}

function renderPagination() {
  const disabledPrev = currentPage <= 1;
  const disabledNext = currentPage >= totalPages;

  return `
    <div class="pager">
      <button id="prevPage" ${disabledPrev ? "disabled" : ""}>Prev</button>
      <span>Page ${currentPage} / ${totalPages}</span>
      <button id="nextPage" ${disabledNext ? "disabled" : ""}>Next</button>

      <label style="margin-left:12px;">
        Page Size:
        <select id="pageSizeSel">
          ${[5,10,20,50].map(n => `<option value="${n}" ${n===pageSize ? "selected":""}>${n}</option>`).join("")}
        </select>
      </label>
    </div>
  `;
}

function renderFilters() {
  return `
    <div class="filters">
      <input id="q" type="text" placeholder="Search by name..." value="${escapeHtml(currentQuery)}" />

      <input id="leagueFilter" type="text" placeholder="Filter by league..." value="${escapeHtml(currentLeague)}" />

      <button id="applyFilters">Apply</button>
      <button id="clearFilters">Clear</button>

      <label style="margin-left:12px;">
        Sort:
        <select id="sortSel">
          ${["name","founded","league","country"].map(s => `<option value="${s}" ${s===currentSort?"selected":""}>${s}</option>`).join("")}
        </select>
      </label>

      <label>
        Dir:
        <select id="dirSel">
          <option value="asc" ${currentDir==="asc"?"selected":""}>asc</option>
          <option value="desc" ${currentDir==="desc"?"selected":""}>desc</option>
        </select>
      </label>

      <button id="applySort">Sort</button>
    </div>
  `;
}

function renderList(items) {
  const rows = (items || []).map(t => `
    <div class="team-row">
      <img class="team-thumb"
           src="${safeImg(t.imageUrl, t.name)}"
           alt="${escapeHtml(t.name)} logo"
           onerror="this.onerror=null; this.src='https://placehold.co/80x80?text=${encodeURIComponent((t.name||'Team').slice(0,12))}';" />

      <div class="team-main">
        <div class="team-title">${escapeHtml(t.name)}</div>
        <div class="team-sub">${escapeHtml(t.league)} • ${escapeHtml(t.country)} • Founded ${escapeHtml(t.founded)}</div>
        <div class="team-sub">Stadium: ${escapeHtml(t.stadium)}</div>
      </div>

      <div class="team-actions">
        <button class="editBtn" data-id="${escapeHtml(t.id)}">Edit</button>
        <button class="delBtn" data-id="${escapeHtml(t.id)}">Delete</button>
      </div>
    </div>
  `).join("");

  return `
    ${renderFilters()}
    <h2>Teams (${totalCount})</h2>
    ${renderPagination()}
    <div class="team-list">${rows || "<p>No teams found.</p>"}</div>
  `;
}

async function loadTeams() {
  const params = new URLSearchParams();
  params.set("page", String(currentPage));
  params.set("pageSize", String(pageSize));
  params.set("sort", currentSort);
  params.set("dir", currentDir);

  if (currentQuery) params.set("q", currentQuery);
  if (currentLeague) params.set("league", currentLeague);

  const res = await fetch(`${API_BASE}/teams?${params.toString()}`);
  if (!res.ok) throw new Error(`GET /teams failed (HTTP ${res.status})`);

  const data = await res.json();
  totalCount = data.totalCount || 0;

  // totalPages is derived
  totalPages = Math.max(1, Math.ceil(totalCount / pageSize));

  return data.items || [];
}

async function refreshList() {
  try {
    const items = await loadTeams();
    document.getElementById("listView").innerHTML = renderList(items);

    // Wire pagination
    const prev = document.getElementById("prevPage");
    const next = document.getElementById("nextPage");
    const pageSizeSel = document.getElementById("pageSizeSel");

    if (prev) prev.addEventListener("click", async () => {
      if (currentPage > 1) currentPage--;
      await refreshList();
    });

    if (next) next.addEventListener("click", async () => {
      if (currentPage < totalPages) currentPage++;
      await refreshList();
    });

    if (pageSizeSel) pageSizeSel.addEventListener("change", async (e) => {
      pageSize = parseInt(e.target.value, 10);
      currentPage = 1;
      await refreshList();
    });

    // Wire filters + sorting
    document.getElementById("applyFilters").addEventListener("click", async () => {
      currentQuery = document.getElementById("q").value.trim();
      currentLeague = document.getElementById("leagueFilter").value.trim();
      currentPage = 1;
      await refreshList();
    });

    document.getElementById("clearFilters").addEventListener("click", async () => {
      currentQuery = "";
      currentLeague = "";
      currentPage = 1;
      await refreshList();
    });

    document.getElementById("applySort").addEventListener("click", async () => {
      currentSort = document.getElementById("sortSel").value;
      currentDir = document.getElementById("dirSel").value;
      currentPage = 1;
      await refreshList();
    });

    // Wire edit/delete buttons
    document.querySelectorAll(".editBtn").forEach(btn => {
      btn.addEventListener("click", async () => {
        const id = btn.dataset.id;
        // simplest: find in current DOM data by reloading current page and matching id
        const itemsNow = await loadTeams();
        const team = itemsNow.find(t => String(t.id) === String(id));
        if (!team) return alert("Team not found on this page. Try refreshing.");
        fillForm(team);
        show("form");
      });
    });

    document.querySelectorAll(".delBtn").forEach(btn => {
      btn.addEventListener("click", async () => {
        const id = btn.dataset.id;
        if (!confirm("Delete this team?")) return;

        const res = await fetch(`${API_BASE}/teams/${id}`, { method: "DELETE" });
        if (!res.ok) {
          alert(`Delete failed (HTTP ${res.status})`);
          return;
        }
        await refreshList();
      });
    });

  } catch (e) {
    console.error(e);
    document.getElementById("listView").innerHTML =
      "<p>Could not load list from backend. Make sure backend is running.</p>";
  }
}

async function refreshStats() {
  try {
    const res = await fetch(`${API_BASE}/stats`);
    if (!res.ok) throw new Error(`GET /stats failed (HTTP ${res.status})`);
    const data = await res.json();

    statsTotalCount = data.totalCount || 0;
    statsTeamsPerLeague = data.teamsPerLeague || {};

    const leagueRows = Object.entries(statsTeamsPerLeague)
      .map(([league, count]) => `<li>${escapeHtml(league)}: ${escapeHtml(count)}</li>`)
      .join("");

    document.getElementById("statsView").innerHTML = `
      <h2>Stats</h2>
      <p><strong>Total Teams:</strong> ${escapeHtml(statsTotalCount)}</p>
      <h3>Teams Per League</h3>
      <ul>${leagueRows || "<li>No data.</li>"}</ul>
    `;
  } catch (e) {
    console.error(e);
    document.getElementById("statsView").innerHTML =
      "<p>Could not load stats from backend. Make sure backend is running.</p>";
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  // top nav
  document.getElementById("showList").addEventListener("click", async () => {
    show("list");
    await refreshList();
  });

  document.getElementById("showForm").addEventListener("click", () => {
    clearForm();
    show("form");
  });

  document.getElementById("showStats").addEventListener("click", async () => {
    show("stats");
    await refreshStats();
  });

  document.getElementById("cancel").addEventListener("click", () => show("list"));

  // Submit form: multipart/form-data with optional file
  document.getElementById("teamForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    clearFormErrors();

    const fd = new FormData();
    fd.append("name", document.getElementById("name").value);
    fd.append("league", document.getElementById("league").value);
    fd.append("country", document.getElementById("country").value);
    fd.append("founded", document.getElementById("founded").value);
    fd.append("stadium", document.getElementById("stadium").value);

    const file = document.getElementById("imageFile").files[0];
    if (file) fd.append("image", file);

    const url = editingId
      ? `${API_BASE}/teams/${editingId}`
      : `${API_BASE}/teams`;

    const method = editingId ? "PUT" : "POST";

    try {
      const res = await fetch(url, {
        method,
        body: fd
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

      clearForm();
      show("list");
      await refreshList();
    } catch (err) {
      console.error(err);
      showFormErrors({ form: "Request failed. Check console and backend logs." });
    }
  });

  // initial view
  show("list");
  await refreshList();
});