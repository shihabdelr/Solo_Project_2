/*https://soloproj.netlify.app/*/

const API_BASE = "https://solo-project-2-5s58.onrender.com/api";

let totalCount = 0;
let totalPages = 1;

let statsTotalCount = 0;
let statsTeamsPerLeague = {};


let teams = [];
let currentPage = 1;

let editingId = null;
let nextTeamId = null; 

async function loadTeams(page = 1) {
  const res = await fetch(`${API_BASE}/teams?page=${page}`);
  if (!res.ok) throw new Error(`Failed to load teams (HTTP ${res.status})`);

  const data = await res.json();

  teams = data.items;
  currentPage = data.page;

  totalCount = data.totalCount;
  totalPages = Math.max(1, Math.ceil(totalCount / data.pageSize));

  renderList();
}

async function loadStats() {
  const res = await fetch(`${API_BASE}/stats`);
  if (!res.ok) throw new Error(`Failed to load stats (HTTP ${res.status})`);

  const data = await res.json();
  statsTotalCount = data.totalCount;
  statsTeamsPerLeague = data.teamsPerLeague || {};

  renderStats();
}

function show(view) {
  const listView = document.getElementById("listView");
  const formView = document.getElementById("formView");
  const statsView = document.getElementById("statsView");

  listView.style.display = "none";
  formView.style.display = "none";
  statsView.style.display = "none";

  if (view === "list") {
    listView.style.display = "block";
  } else if (view === "form") {
    formView.style.display = "block";
  } else if (view === "stats") {
    statsView.style.display = "block";
  }
}

function renderList() {
  const list = document.getElementById("listView");

  const startNum = totalCount === 0 ? 0 : (currentPage - 1) * 10 + 1;
  const endNum = Math.min(currentPage * 10, totalCount);

  const prevDisabled = currentPage <= 1 ? "disabled" : "";
  const nextDisabled = currentPage >= totalPages ? "disabled" : "";

  let html = `
    <h2>Teams</h2>

    <div style="display:flex; align-items:center; gap:10px; margin:10px 0;">
      <button id="prevPage" ${prevDisabled}>Previous</button>
      <div><b>Page ${currentPage}</b> of ${totalPages}</div>
      <button id="nextPage" ${nextDisabled}>Next</button>
      <div style="margin-left:auto;">Showing ${startNum}–${endNum} of ${totalCount}</div>
    </div>

    <table border="1" cellpadding="6">
      <tr>
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
        <td>${t.name}</td>
        <td>${t.league}</td>
        <td>${t.country}</td>
        <td>${t.founded}</td>
        <td>${t.stadium || ""}</td>
        <td>
          <button onclick="editTeam('${t.id}')">Edit</button>
          <button onclick="deleteTeam('${t.id}')">Delete</button>
        </td>
      </tr>
    `;
  }

  html += `</table>`;
  list.innerHTML = html;

  document.getElementById("prevPage")?.addEventListener("click", () => {
    if (currentPage > 1) loadTeams(currentPage - 1);
  });

  document.getElementById("nextPage")?.addEventListener("click", () => {
    if (currentPage < totalPages) loadTeams(currentPage + 1);
  });
}

function renderStats() {
  const stats = document.getElementById("statsView");

  let list = "<ul>";
  for (const league in statsTeamsPerLeague) {
    list += `<li>${league}: ${statsTeamsPerLeague[league]}</li>`;
  }
  list += "</ul>";

  stats.innerHTML = `
    <h2>Stats</h2>
    <p><b>Total teams (entire dataset):</b> ${statsTotalCount}</p>
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

  if (team !== null) {
    nameInput.value = team.name;
    leagueInput.value = team.league;
    countryInput.value = team.country;
    foundedInput.value = team.founded;
    stadiumInput.value = team.stadium;
  } else {
    nameInput.value = "";
    leagueInput.value = "";
    countryInput.value = "";
    foundedInput.value = "";
    stadiumInput.value = "";
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
    const newTotalPages = Math.max(1, Math.ceil(newTotal / 10));
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
      stadium: document.getElementById("stadium").value
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
        const newTotalPages = Math.max(1, Math.ceil(newTotal / 10));
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

  show("list");
  loadTeams(1).catch((err) => {
    console.error(err);
    alert("Could not load teams from backend. Make sure Flask is running on 127.0.0.1:5000.");
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
    html += `<li><b>${field}:</b> ${errors[field]}</li>`;
  }
  html += "</ul>";

  box.innerHTML = html;
  box.style.display = "block";
}