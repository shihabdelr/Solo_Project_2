from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import os
import math
from urllib.parse import quote

app = Flask(__name__)
CORS(app)

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "teams.json")

# Step 2: Configurable paging
ALLOWED_PAGE_SIZES = {5, 10, 20, 50}
DEFAULT_PAGE_SIZE = 10


def load_data():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    tmp_path = DATA_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, DATA_FILE)


# Step 3: Placeholder image URL
def placeholder_image_url(team_name: str) -> str:
    label = (team_name or "Team")[:12]
    return f"https://placehold.co/80x80?text={quote(label)}"


def normalize_image_url(team_name: str, image_url: str) -> str:
    """If empty, return placeholder. If provided, must be http(s)."""
    if not image_url:
        return placeholder_image_url(team_name)
    if image_url.startswith("http://") or image_url.startswith("https://"):
        return image_url
    return ""  # invalid marker (caller should add validation error)


@app.get("/")
def home():
    return "Backend is running", 200


@app.get("/api/teams")
def get_teams():
    # ---- Page size (Step 2) ----
    raw_page_size = request.args.get("pageSize", str(DEFAULT_PAGE_SIZE))
    try:
        page_size = int(raw_page_size)
    except ValueError:
        page_size = DEFAULT_PAGE_SIZE
    if page_size not in ALLOWED_PAGE_SIZES:
        page_size = DEFAULT_PAGE_SIZE

    # ---- Page ----
    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        page = 1
    if page < 1:
        page = 1

    data = load_data()
    teams = data.get("teams", [])

    # ---- Filter / Search (Step 4) ----
    q = (request.args.get("q", "") or "").strip().lower()
    league_filter = (request.args.get("league", "") or "").strip().lower()

    filtered = teams

    if q:
        filtered = [t for t in filtered if q in str(t.get("name", "")).lower()]

    if league_filter:
        filtered = [
            t for t in filtered
            if str(t.get("league", "")).strip().lower() == league_filter
        ]

    # ---- Sorting (Step 4) ----
    sort_field = (request.args.get("sort", "name") or "name").strip().lower()
    sort_dir = (request.args.get("dir", "asc") or "asc").strip().lower()

    allowed_sort_fields = {"name", "founded", "league", "country"}
    if sort_field not in allowed_sort_fields:
        sort_field = "name"

    reverse = sort_dir == "desc"

    def sort_key(t):
        if sort_field == "founded":
            try:
                return int(t.get("founded"))
            except (TypeError, ValueError):
                return 10**9
        return str(t.get(sort_field, "")).lower()

    filtered.sort(key=sort_key, reverse=reverse)

    # ---- Paging (after filter/sort) ----
    total_count = len(filtered)

    total_pages = max(1, math.ceil(total_count / page_size)) if total_count else 1
    if page > total_pages:
        page = total_pages

    start = (page - 1) * page_size
    end = start + page_size
    items = filtered[start:end] if start < total_count else []

    # Step 3: guarantee imageUrl for display even if seed data lacks it
    for t in items:
        if not t.get("imageUrl"):
            t["imageUrl"] = placeholder_image_url(t.get("name", "Team"))

    return jsonify({
        "items": items,
        "totalCount": total_count,
        "page": page,
        "pageSize": page_size
    })


@app.get("/api/stats")
def get_stats():
    data = load_data()
    teams = data.get("teams", [])

    total_count = len(teams)

    teams_per_league = {}
    for t in teams:
        league = t.get("league", "Unknown")
        teams_per_league[league] = teams_per_league.get(league, 0) + 1

    return jsonify({
        "totalCount": total_count,
        "teamsPerLeague": teams_per_league
    })


@app.put("/api/teams/<team_id>")
def update_team(team_id):
    payload = request.get_json(silent=True) or {}
    errors = {}

    def get_str(field):
        v = payload.get(field, "")
        return v.strip() if isinstance(v, str) else ""

    name = get_str("name")
    league = get_str("league")
    country = get_str("country")
    stadium = get_str("stadium")
    image_url_raw = get_str("imageUrl")

    founded_raw = payload.get("founded", "")
    try:
        founded = int(founded_raw)
    except (TypeError, ValueError):
        founded = None

    if not name:
        errors["name"] = "Name is required."
    if not league:
        errors["league"] = "League is required."
    if not country:
        errors["country"] = "Country is required."
    if founded is None:
        errors["founded"] = "Founded must be a number."
    elif founded < 1701:
        errors["founded"] = "Founded must be 1701 or later."
    if not stadium:
        errors["stadium"] = "Stadium is required."

    normalized_image = normalize_image_url(name, image_url_raw)
    if image_url_raw and not normalized_image:
        errors["imageUrl"] = "Image URL must start with http:// or https://"

    data = load_data()
    teams = data.get("teams", [])

    idx = None
    for i, t in enumerate(teams):
        if str(t.get("id")) == str(team_id):
            idx = i
            break

    if idx is None:
        return jsonify({"error": "Team not found."}), 404

    # uniqueness check by name
    lower = name.lower()
    for t in teams:
        if str(t.get("id")) != str(team_id) and str(t.get("name", "")).strip().lower() == lower:
            errors["name"] = "A team with this name already exists."
            break

    if errors:
        return jsonify({"errors": errors}), 400

    teams[idx]["name"] = name
    teams[idx]["league"] = league
    teams[idx]["country"] = country
    teams[idx]["founded"] = founded
    teams[idx]["stadium"] = stadium
    teams[idx]["imageUrl"] = normalized_image or placeholder_image_url(name)

    data["teams"] = teams
    save_data(data)

    return jsonify(teams[idx]), 200


@app.delete("/api/teams/<team_id>")
def delete_team(team_id):
    data = load_data()
    teams = data.get("teams", [])

    idx = None
    for i, t in enumerate(teams):
        if str(t.get("id")) == str(team_id):
            idx = i
            break

    if idx is None:
        return jsonify({"error": "Team not found."}), 404

    deleted = teams.pop(idx)
    data["teams"] = teams
    save_data(data)

    return jsonify({"deletedId": str(deleted.get("id"))}), 200


@app.post("/api/teams")
def create_team():
    payload = request.get_json(silent=True) or {}
    errors = {}

    def get_str(field):
        v = payload.get(field, "")
        return v.strip() if isinstance(v, str) else ""

    name = get_str("name")
    league = get_str("league")
    country = get_str("country")
    stadium = get_str("stadium")
    image_url_raw = get_str("imageUrl")

    founded_raw = payload.get("founded", "")
    try:
        founded = int(founded_raw)
    except (TypeError, ValueError):
        founded = None

    if not name:
        errors["name"] = "Name is required."
    if not league:
        errors["league"] = "League is required."
    if not country:
        errors["country"] = "Country is required."
    if founded is None:
        errors["founded"] = "Founded must be a number."
    elif founded < 1701:
        errors["founded"] = "Founded must be 1701 or later."
    if not stadium:
        errors["stadium"] = "Stadium is required."

    normalized_image = normalize_image_url(name, image_url_raw)
    if image_url_raw and not normalized_image:
        errors["imageUrl"] = "Image URL must start with http:// or https://"

    data = load_data()
    teams = data.get("teams", [])

    # uniqueness check by name
    if name:
        lower = name.lower()
        for t in teams:
            if str(t.get("name", "")).strip().lower() == lower:
                errors["name"] = "A team with this name already exists."
                break

    if errors:
        return jsonify({"errors": errors}), 400

    next_id = int(data.get("nextId", len(teams) + 1))

    new_team = {
        "id": str(next_id),
        "name": name,
        "league": league,
        "country": country,
        "founded": founded,
        "stadium": stadium,
        "imageUrl": normalized_image or placeholder_image_url(name)
    }

    teams.append(new_team)
    data["teams"] = teams
    data["nextId"] = next_id + 1

    save_data(data)
    return jsonify(new_team), 201


if __name__ == "__main__":
    app.run(debug=True)