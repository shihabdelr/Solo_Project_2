Solo Project 3 — Soccer Teams Collection Manager

Domain name + registrar
  Domain: https://solo-project-2-7rmr.onrender.com`
  Registrar: N/A this is a Render-provided onrender.com subdomain, not a custom purchased domain

Hosting provider
  Render
    Web Service: Flask backend + serves the frontend files
    Render Postgres: managed PostgreSQL database

Tech stack
  Backend: Python + Flask, gunicorn (production server), psycopg2 (Postgres driver)
  Frontend: HTML + CSS + Vanilla JavaScript (served by Flask)
  API: REST-style JSON endpoints under /api/*
  File uploads (images): saved under backend/static/uploads/ and referenced as /static/uploads/<filename>

Database type & where it is hosted
  Database: PostgreSQL
  Hosted on: Render (managed Postgres instance attached to the project)
  Connection: via `DATABASE_URL` environment variable

## How to deploy and update the app

Initial deploy (Render)
1. Push code to GitHub.
2. Create a "Render Web Service" connected to the GitHub repo.
3. Set the service start command to run Gunicorn:
    I used: gunicorn app:app --bind 0.0.0.0:$PORT
4. Create a "Render Postgres" database in the same project.
5. Add the database connection string as an environment variable:
    `DATABASE_URL` = (Render Postgres “External Database URL” or “Internal Database URL”, depending on your setup)

Update / redeploy
  Push a new commit to the connected GitHub branch.
  If auto-deploy is enabled, Render redeploys automatically.
  Else: Render Dashboard → Web Service → Manual Deploy → “Deploy latest commit”.

Local development:
  From the backend/ folder:

1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   # Windows: .venv\Scripts\activate
   # Mac/Linux: source .venv/bin/activate
   pip install -r requirements.txt