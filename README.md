# FindIt

[![CI](https://github.com/monkeprogrammer01/findit/actions/workflows/ci.yml/badge.svg)](https://github.com/monkeprogrammer01/findit/actions/workflows/ci.yml)

**Automated University & Campus Lost and Found Management System**

## Team 404

| Member | Student ID |
| --- | --- |
| Yerkebulan Kenzhegali | 240107051 |
| Arsen Seitkali | 240107064 |
| Begzhan Imangali | 240107042 |
| Zhumash Nurdaulet | 240107053 |

## Problem

On university campuses, lost and found is split across physical security desks,
social media channels (Telegram, WhatsApp, Instagram) and paper notice boards.
Matches are slow, storage backlogs grow, ownership claims are hard to verify, and
campus administration has no operational visibility.

FindIt centralises lost-item reports and found-item cataloging, matches items on
structured metadata (category, location, date, attributes), and records a verified
handover to the rightful owner.

## Scope

**In scope**

- Digital lost-item reporting and found-item cataloging
- Metadata tag matching (category, location, date, attributes)
- Claim verification with secret verification questions
- Admin dashboard for physical desk inventory and handover logging
- Automated email/SMS status notifications

**Out of scope**

- Shipping or courier delivery
- RFID/Bluetooth hardware tracking tags
- Monetary rewards or escrow payments
- Public off-campus / citywide marketplace

## Architecture

FindIt is a **layered modular monolith**: one application container with four
layers (interface, application, domain, infrastructure), a relational database
and a photo store. Identity comes from University SSO; notifications go through an
email/SMS gateway.

- Container diagram: [docs/architecture/container-diagram.md](docs/architecture/container-diagram.md)
- ADR-001: [docs/adr/ADR-001-university-sso.md](docs/adr/ADR-001-university-sso.md)
- ADR-002: [docs/adr/ADR-002-claim-state-pattern.md](docs/adr/ADR-002-claim-state-pattern.md)

## Tech stack

- Backend: Python, FastAPI
- Frontend: React
- Database: PostgreSQL
- Deployment: Docker

## Project layout

```
backend/
  app/
    interface/       # HTTP API (FastAPI routers)
    application/     # use cases: reports, cataloging, matching, claims, handover, retention
    domain/          # item, claim and match rules
    infrastructure/  # database, photo store, SSO, email/SMS gateway
  tests/
frontend/            # React web application
docs/
docker-compose.yml   # local infrastructure (PostgreSQL)
.env.example         # template for .env
```

## Running with Docker

Requires Docker with Docker Compose v2.

1. Create your local environment file and adjust the values:

   ```bash
   cp .env.example .env
   ```

   If port 5432 or 8000 is already taken on your machine, set another one in
   `POSTGRES_PORT` / `BACKEND_PORT` (for example `5433`).

2. Build and start PostgreSQL and the backend:

   ```bash
   docker compose up -d --build
   ```

3. Check that both services are ready. `STATUS` should show `(healthy)`:

   ```bash
   docker compose ps
   ```

The API is served at http://localhost:8000 (interactive docs at `/docs`).
The backend waits until the database is healthy before it starts.

Connect to the database from your machine with
`postgresql://<POSTGRES_USER>:<POSTGRES_PASSWORD>@localhost:<POSTGRES_PORT>/<POSTGRES_DB>`,
or open a psql shell inside the container:

```bash
docker compose exec db psql -U <POSTGRES_USER> -d <POSTGRES_DB>
```

Stop the services with `docker compose down`. Database data and uploaded
photos are kept in the `pgdata` and `photos` volumes; `docker compose down -v`
deletes them.

## API overview

Interactive docs: http://localhost:8000/docs. In local mode get a test token with
`POST /dev-sso/token?role=student|desk_admin|sys_admin` and press **Authorize**.

| Area | Endpoints | Who |
| --- | --- | --- |
| Lost reports (FR-01) | `POST /lost-reports`, `GET /lost-reports/me`, `GET/PATCH/DELETE /lost-reports/{id}` | author |
| Matches (FR-03) | `GET /lost-reports/{id}/matches` | author, staff |
| Found items (FR-02) | `POST /found-items`, `POST /found-items/{id}/photos`, `GET /found-items/{id}/full` | desk_admin |
| Search | `GET /found-items?q=&category=&location=&date_from=&date_to=&color=&limit=&offset=` | everyone |
| Item card | `GET /found-items/{id}`, `GET /found-items/{id}/questions`, `GET /found-items/{id}/photos/{name}` | everyone |
| Claims (FR-04) | `POST /found-items/{id}/claims`, `GET /claims/me` | student |
| Claim review | `GET /claims?status=`, `GET /claims/{id}`, `POST /claims/{id}/approve`, `POST /claims/{id}/reject` | desk_admin |
| Handover (FR-05) | `POST /claims/{id}/handover` | desk_admin |

Public item responses never contain the storage location, serial number or
verification answers. New found items are matched against open lost reports
right away (and new lost reports against stored items); authors get an email.

Emails go to **MailHog** in local development: open http://localhost:8025 to see
every message the backend sent.

## Running the backend locally

For day-to-day development with auto-reload, run only the database in Docker
and the backend on your machine:

```bash
docker compose up -d db

cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Before pushing, run the same checks as CI (from `backend/`):

```bash
ruff check .          # lint
ruff format .         # auto-format
pytest                # tests
```

## CI

GitHub Actions ([.github/workflows/ci.yml](.github/workflows/ci.yml)) runs on
every pull request and on pushes to `main`:

- **Backend lint and tests**: `ruff check`, `ruff format --check`, `pytest`
- **Backend Docker image**: builds `backend/Dockerfile`