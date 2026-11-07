# FindIt

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

## Running the infrastructure

Requires Docker with Docker Compose v2.

1. Create your local environment file and adjust the values:

   ```bash
   cp .env.example .env
   ```

   If port 5432 is already taken on your machine, set another one in
   `POSTGRES_PORT` (for example `5433`).

2. Start PostgreSQL:

   ```bash
   docker compose up -d
   ```

3. Check that the database is ready. `STATUS` should show `(healthy)`:

   ```bash
   docker compose ps
   ```

Connect from your machine with
`postgresql://<POSTGRES_USER>:<POSTGRES_PASSWORD>@localhost:<POSTGRES_PORT>/<POSTGRES_DB>`,
or open a psql shell inside the container:

```bash
docker compose exec db psql -U <POSTGRES_USER> -d <POSTGRES_DB>
```

Stop the services with `docker compose down`. Data is kept in the `pgdata`
volume; `docker compose down -v` deletes it.

## Running the backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API is served at http://localhost:8000 (interactive docs at `/docs`).
Run the tests with `pytest`.