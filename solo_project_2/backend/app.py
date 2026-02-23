from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import json
import os
import math
from urllib.parse import quote
import psycopg2
from psycopg2 import errors as pg_errors
from werkzeug.utils import secure_filename
import uuid

# Serve /static/* from backend/static
app = Flask(__name__, static_folder="static", static_url_path="/static")
CORS(app)

# --- Paths ---
BASE_DIR = os.path.dirname(__file__)

# Support both locations, so seed works whether teams.json is in backend/data or backend/
DATA_FILE_CANDIDATES = [
    os.path.join(BASE_DIR, "data", "teams.json"),
    os.path.join(BASE_DIR, "teams.json"),
]

UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- Paging ---
ALLOWED_PAGE_SIZES = {5, 10, 20, 50}
DEFAULT_PAGE_SIZE = 10

# --- DB ---
_db_initialized = False


def get_db_conn():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")

    # Fail fast + enforce SSL (Render Postgres expects SSL)
    return psycopg2.connect(
        url,
        sslmode="require",
        connect_timeout=5,
        options="-c statement_timeout=5000",
    )


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


def ensure_db_initialized():
    global _db_initialized
    if not _db_initialized:
        init_db()
        _db_initialized = True


@app.before_request
def lazy_init_db():
    """
    Avoid DB work for basic static/front-end routes so Render can start quickly.
    Only initialize DB for API routes that need tables.
    """
    if request.method == "OPTIONS":
        return

    # Frontend + static should never block on DB
    if request.path in ["/", "/index.html", "/app.js", "/style.css", "/favicon.ico"]:
        return
    if request.path.startswith("/static/"):
        return

    # Health endpoints: /api/health doesn't need DB, /api/health/db does its own connect test
    if request.path in ["/api/health", "/api/health/db"]:
        return

    # Everything else under /api should ensure tables exist
    if request.path.startswith("/api/"):
        ensure_db_initialized()


# --- JSON seed helpers ---
def find_data_file():
    for p in DATA_FILE_CANDIDATES:
        if os.path.exists(p):
            return p
    return DATA_FILE_CANDIDATES[0]


def load_data():
    path = find_data_file()
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# --- Normalizers ---
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


# --- Image helpers ---
def placeholder_image_url(team_name: str) -> str:
    label = (team_name or "Team")[:12]
    return f"https://placehold.co/80x80?text={quote(label)}"


def allowed_image_filename(filename: str) -> bool:
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_IMAGE_EXTS


def save_uploaded_image(file_storage):
    """
    Saves an uploaded image to backend/static/uploads and returns public URL path,
    e.g. /static/uploads/abc123.jpg
    """
    if not file_storage or not file_storage.filename:
        return None

    filename = secure_filename(file_storage.filename)
    if not allowed_image_filename(filename):
        raise ValueError("Unsupported file type. Allowed: png, jpg, jpeg, gif, webp")

    ext = os.path.splitext(filename)[1].lower()
    unique_name = f"{uuid.uuid4().hex}{ext}"

    save_path = os.path.join(UPLOAD_DIR, unique_name)
    file_storage.save(save_path)

    return f"/static/uploads/{unique_name}"


# -----------------------
# Frontend serving routes
# -----------------------
@app.get("/")
def serve_index():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/index.html")
def serve_index_explicit():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/app.js")
def serve_app_js():
    return send_from_directory(BASE_DIR, "app.js")


@app.get("/style.css")
def serve_style_css():
    return send_from_directory(BASE_DIR, "style.css")


# -------------
# API endpoints
# -------------
@app.get("/api/health")
def health():
    return jsonify({"ok": True}), 200


@app.get("/api/health/db")
def health_db():
    try:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
        return jsonify({"ok": True}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


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
        params["league"] = f"%{league_filter}%"

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    offset = (page - 1) * page_size

    count_sql = f"SELECT COUNT(*) FROM teams {where_sql};"

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


@app.post("/api/upload")
def upload_image():
    """
    Optional helper endpoint if you ever want to upload first, then save the URL.
    Frontend in this solution uploads as part of create/update, so you may not use this.
    """
    if "image" not in request.files:
        return jsonify({"error": "No file provided. Use form field name 'image'."}), 400

    img = request.files["image"]
    try:
        image_url = save_uploaded_image(img)
        return jsonify({"ok": True, "imageUrl": image_url}), 201
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": f"Upload failed: {e}"}), 500


@app.post("/api/teams")
def create_team():
    # multipart/form-data
    name = (request.form.get("name") or "").strip()
    league = (request.form.get("league") or "").strip()
    country = (request.form.get("country") or "").strip()
    stadium = (request.form.get("stadium") or "").strip()

    founded_raw = request.form.get("founded")
    try:
        founded = int(founded_raw)
    except (TypeError, ValueError):
        founded = None

    errors = {}
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

    image_url = None
    if "image" in request.files and request.files["image"].filename:
        try:
            image_url = save_uploaded_image(request.files["image"])
        except ValueError as ve:
            errors["image"] = str(ve)
        except Exception as e:
            errors["image"] = f"Upload failed: {e}"

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


@app.put("/api/teams/<team_id>")
def update_team(team_id):
    # multipart/form-data
    name = (request.form.get("name") or "").strip()
    league = (request.form.get("league") or "").strip()
    country = (request.form.get("country") or "").strip()
    stadium = (request.form.get("stadium") or "").strip()

    founded_raw = request.form.get("founded")
    try:
        founded = int(founded_raw)
    except (TypeError, ValueError):
        founded = None

    errors = {}
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

    # get existing image
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT image_url FROM teams WHERE id=%s;", (team_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Team not found."}), 404
            existing_image_url = row[0]

    new_image_url = None
    if "image" in request.files and request.files["image"].filename:
        try:
            new_image_url = save_uploaded_image(request.files["image"])
        except ValueError as ve:
            errors["image"] = str(ve)
        except Exception as e:
            errors["image"] = f"Upload failed: {e}"

    if errors:
        return jsonify({"errors": errors}), 400

    image_url = new_image_url or existing_image_url or placeholder_image_url(name)

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
            updated = cur.fetchone()
        conn.commit()

    if not updated:
        return jsonify({"error": "Team not found."}), 404

    return jsonify({"ok": True, "imageUrl": image_url}), 200


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


@app.post("/api/admin/seed")
def seed_db():
    """
    One-time seed route: loads teams from the JSON file into Postgres.
    Safe to run multiple times (skips duplicates by team name).
    """
    ensure_db_initialized()

    try:
        data = load_data()
        seed_teams = data.get("teams", [])
    except Exception as e:
        return jsonify({"error": f"Failed to read seed JSON: {e}", "tried": find_data_file()}), 500

    if not seed_teams:
        return jsonify({"error": "Seed JSON contained no teams."}), 400

    inserted = 0
    skipped = 0

    sql = """
        INSERT INTO teams (name, league, country, founded, stadium, image_url)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (name) DO NOTHING;
    """

    conn = None
    try:
        conn = get_db_conn()
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

                # If seed has a URL, keep it; otherwise placeholder
                image_url = str(t.get("imageUrl", "")).strip()
                if not image_url:
                    image_url = placeholder_image_url(name)

                if not name or not league or not country or not stadium:
                    skipped += 1
                    continue

                cur.execute(sql, (name, league, country, founded, stadium, image_url))
                if cur.rowcount == 1:
                    inserted += 1
                else:
                    skipped += 1

        conn.commit()

    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"error": f"Seeding failed: {e}"}), 500
    finally:
        if conn:
            conn.close()

    return jsonify({
        "ok": True,
        "inserted": inserted,
        "skipped": skipped,
        "total_in_seed_file": len(seed_teams),
        "seed_file_used": find_data_file(),
    }), 200


if __name__ == "__main__":
    # Local dev only. Render uses gunicorn.
    app.run(debug=True)