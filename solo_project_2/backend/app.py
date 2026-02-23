from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import os
import math
from urllib.parse import quote
import psycopg2

app = Flask(__name__)
CORS(app)

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "teams.json")

# Step 2: Configurable paging
ALLOWED_PAGE_SIZES = {5, 10, 20, 50}
DEFAULT_PAGE_SIZE = 10

def get_db_conn():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg2.connect(url, sslmode="require")

def init_db():
    schema = """
    CREATE TABLE IF NOT EXISTS teams (
      id SERIAL PRIMARY KEY,
      name TEXT NOT NULL UNIQUE,
      league TEXT NOT NULL,
      country TEXT NOT NULL,
      founded INTEGER NOT NULL CHECK (founded >= 1701),
      stadium TEXT NOT NULL,
      image_url TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_teams_league ON teams(league);
    CREATE INDEX IF NOT EXISTS idx_teams_name ON teams(name);
    """
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(schema)

def normalize_page_size(raw):
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_PAGE_SIZE
    return n if n in ALLOWED_PAGE_SIZES else DEFAULT_PAGE_SIZE


def normalize_page(raw):
    try:
        p = int(raw)
    except (TypeError, ValueError):
        return 1
    return p if p >= 1 else 1


def normalize_sort(sort_field, sort_dir):
    allowed = {"name", "founded", "league", "country"}
    sf = (sort_field or "name").strip().lower()
    if sf not in allowed:
        sf = "name"
    sd = (sort_dir or "asc").strip().lower()
    if sd not in {"asc", "desc"}:
        sd = "asc"
    return sf, sd
'''
def load_data():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    tmp_path = DATA_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, DATA_FILE)

'''
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
    page_size = normalize_page_size(request.args.get("pageSize", DEFAULT_PAGE_SIZE))
    page = normalize_page(request.args.get("page", 1))

    q = (request.args.get("q", "") or "").strip()
    league_filter = (request.args.get("league", "") or "").strip()

    sort_field, sort_dir = normalize_sort(
        request.args.get("sort", "name"),
        request.args.get("dir", "asc"),
    )

    where_clauses = []
    params = {}

    if q:
        where_clauses.append("name ILIKE %(q)s")
        params["q"] = f"%{q}%"

    if league_filter:
        where_clauses.append("league ILIKE %(league)s")
        params["league"] = league_filter

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    offset = (page - 1) * page_size

    # COUNT (filtered total)
    count_sql = f"SELECT COUNT(*) FROM teams {where_sql};"

    # LIST (filtered + sorted + paged)
    list_sql = f"""
        SELECT id, name, league, country, founded, stadium, image_url
        FROM teams
        {where_sql}
        ORDER BY {sort_field} {sort_dir}
        LIMIT %(limit)s OFFSET %(offset)s;
    """
    params["limit"] = page_size
    params["offset"] = offset

    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(count_sql, params)
            total_count = cur.fetchone()[0]

            # Clamp page if it’s out of range (for UI consistency)
            total_pages = max(1, math.ceil(total_count / page_size)) if total_count else 1
            if page > total_pages:
                page = total_pages
                offset = (page - 1) * page_size
                params["offset"] = offset

            cur.execute(list_sql, params)
            rows = cur.fetchall()

    items = []
    for (id_, name, league, country, founded, stadium, image_url) in rows:
        items.append({
            "id": str(id_),
            "name": name,
            "league": league,
            "country": country,
            "founded": founded,
            "stadium": stadium,
            "imageUrl": image_url,
        })

    return jsonify({
        "items": items,
        "totalCount": total_count,
        "page": page,
        "pageSize": page_size,
    })

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
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM teams;")
            total_count = cur.fetchone()[0]

            cur.execute("""
                SELECT league, COUNT(*)
                FROM teams
                GROUP BY league
                ORDER BY league;
            """)
            rows = cur.fetchall()

    teams_per_league = {league: count for league, count in rows}

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

    try:
        founded = int(payload.get("founded"))
    except (TypeError, ValueError):
        founded = None

    if not name:
        errors["name"] = "Name is required."
    if not league:
        errors["league"] = "League is required."
    if not country:
        errors["country"] = "Country is required."
    if founded is None or founded < 1701:
        errors["founded"] = "Founded must be >= 1701."
    if not stadium:
        errors["stadium"] = "Stadium is required."

    image_url = normalize_image_url(name, image_url_raw)
    if image_url_raw and not image_url:
        errors["imageUrl"] = "Image URL must start with http:// or https://"

    if errors:
        return jsonify({"errors": errors}), 400

    if not image_url:
        image_url = placeholder_image_url(name)

    sql = """
        UPDATE teams
        SET name=%s, league=%s, country=%s,
            founded=%s, stadium=%s, image_url=%s
        WHERE id=%s
        RETURNING id;
    """

    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (name, league, country, founded, stadium, image_url, team_id))
            row = cur.fetchone()
        conn.commit()

    if not row:
        return jsonify({"error": "Team not found."}), 404

    return jsonify({"ok": True}), 200


@app.delete("/api/teams/<team_id>")
def delete_team(team_id):
    sql = "DELETE FROM teams WHERE id=%s RETURNING id;"

    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (team_id,))
            row = cur.fetchone()
        conn.commit()

    if not row:
        return jsonify({"error": "Team not found."}), 404

    return jsonify({"deletedId": str(row[0])}), 200


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

    try:
        founded = int(payload.get("founded"))
    except (TypeError, ValueError):
        founded = None

    if not name:
        errors["name"] = "Name is required."
    if not league:
        errors["league"] = "League is required."
    if not country:
        errors["country"] = "Country is required."
    if founded is None or founded < 1701:
        errors["founded"] = "Founded must be a number >= 1701."
    if not stadium:
        errors["stadium"] = "Stadium is required."

    image_url = normalize_image_url(name, image_url_raw)
    if image_url_raw and not image_url:
        errors["imageUrl"] = "Image URL must start with http:// or https://"

    if errors:
        return jsonify({"errors": errors}), 400

    if not image_url:
        image_url = placeholder_image_url(name)

    sql = """
        INSERT INTO teams (name, league, country, founded, stadium, image_url)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id;
    """

    try:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (name, league, country, founded, stadium, image_url))
                new_id = cur.fetchone()[0]
            conn.commit()
    except psycopg2.errors.UniqueViolation:
        return jsonify({"errors": {"name": "A team with this name already exists."}}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "id": str(new_id),
        "name": name,
        "league": league,
        "country": country,
        "founded": founded,
        "stadium": stadium,
        "imageUrl": image_url
    }), 201

@app.post("/api/admin/seed")
def seed_db():
    """
    One-time seed route: loads teams from the JSON file into Postgres.
    Safe to run multiple times (skips duplicates by team name).
    """
    # Load JSON seed file
    try:
        data = load_data()  # uses DATA_FILE
        seed_teams = data.get("teams", [])
    except Exception as e:
        return jsonify({"error": f"Failed to read seed JSON: {e}"}), 500

    if not seed_teams:
        return jsonify({"error": "Seed JSON contained no teams."}), 400

    inserted = 0
    skipped = 0

    sql = """
        INSERT INTO teams (name, league, country, founded, stadium, image_url)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (name) DO NOTHING;
    """

    try:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                for t in seed_teams:
                    name = str(t.get("name", "")).strip()
                    league = str(t.get("league", "")).strip()
                    country = str(t.get("country", "")).strip()
                    stadium = str(t.get("stadium", "")).strip()

                    founded_raw = t.get("founded")
                    try:
                        founded = int(founded_raw)
                    except (TypeError, ValueError):
                        founded = 1900

                    image_url = str(t.get("imageUrl", "")).strip()
                    image_url = normalize_image_url(name, image_url)
                    if not image_url:
                        image_url = placeholder_image_url(name)

                    # Basic required-field guard (skip bad rows)
                    if not name or not league or not country or not stadium:
                        skipped += 1
                        continue

                    cur.execute(sql, (name, league, country, founded, stadium, image_url))

                    # rowcount == 1 means inserted, 0 means conflict/ignored
                    if cur.rowcount == 1:
                        inserted += 1
                    else:
                        skipped += 1

            conn.commit()

    except Exception as e:
        return jsonify({"error": f"Seeding failed: {e}"}), 500

    return jsonify({
        "ok": True,
        "inserted": inserted,
        "skipped": skipped,
        "total_in_seed_file": len(seed_teams)
    }), 200

try:
    init_db()
    print("Database initialized successfully.")
except Exception as e:
    print("Database initialization failed:", e)

if __name__ == "__main__":
    app.run(debug=True)