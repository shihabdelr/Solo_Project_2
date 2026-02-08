Solo Project 2

This project is a cloud hosted collection manager built using a client/server architecture. The frontend is implemented with HTML, CSS, and JavaScript and is deployed on Netlify, while the backend is a Flask application hosted on Render. All data is persisted on the server using JSON files, so that it maintains its state across refreshes, incognito sessions, and different devices. The application supports full CRUD functionality through backend API routes, enforces server-side validation, and implements fixed paging with 10 records per page. A stats view includes total record counts and domain-specific metrics. This project shows proper separation of concerns, HTTP-based client/server communication, and server-side data persistence.

Frontend URL: https://soloproj.netlify.app/

Backend Base URL: https://solo-project-2-5s58.onrender.com/api

Languages
Frontend: HTML, CSS, JavaScript
Backend: Python Flask

All records are stored on the server in a JSON file: `backend/data/teams.json`

API Routes
`GET /api/teams?page=1`: 10 page list
`POST /api/teams`: create a new record (server validation)
`PUT /api/teams/<id>`: update an existing record (server validation)
`DELETE /api/teams/<id>`: delete a record (with confirmation on client)
`GET /api/stats`: total records + teams-per-league stats


Input Validation
Client-side: required fields in form + basic input constraints
Server-side: required fields, founded must be numeric and >= 1701, unique team name