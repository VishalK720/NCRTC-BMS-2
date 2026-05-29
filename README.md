# NCRTC Bus Management System (BMS)

Enterprise transit operations platform for NCRTC depots: fleet tracking, duty scheduling, incident management, and driver communications.

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

| Service  | URL                    |
|----------|------------------------|
| Frontend | http://localhost:5173  |
| API      | http://localhost:8000  |
| Health   | http://localhost:8000/health |
| Postgres | localhost:5432         |

The stack starts **db** (PostGIS), **backend** (FastAPI + migrations + seed), **frontend** (Vite/React), and **ticker** (GPS simulation every 8s).

## Demo credentials

All accounts use password: **`password`**

| Role              | Username    | Login redirects to      |
|-------------------|-------------|-------------------------|
| Admin             | `admin1`    | Dashboard (`/`)         |
| Admin             | `admin2`    | Dashboard (`/`)         |
| Control operator  | `operator1` | Dashboard (`/`)         |
| Depot manager     | `manager1`  | Dashboard (depot 1)     |
| Depot manager     | `manager2`–`manager4` | Dashboard (depots 2–4) |
| Driver            | `driver1`–`driver70` | Driver app (`/driver`) |

## Screenshots

<!-- Replace with your own captures after `docker compose up` -->

| Module        | Placeholder |
|---------------|-------------|
| AVLS live map | `docs/screenshots/avls-map.png` |
| Scheduling roster | `docs/screenshots/scheduling.png` |
| Incidents     | `docs/screenshots/incidents.png` |
| Driver app    | `docs/screenshots/driver-app.png` |

## Architecture

Four operational modules share one PostgreSQL database and JWT-authenticated API:

```text
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Frontend   │────▶│   Backend   │────▶│  PostGIS DB │
│  React/Vite │     │   FastAPI   │     │             │
└─────────────┘     └──────┬──────┘     └──────▲──────┘
                           │                    │
                    ┌──────▼──────┐             │
                    │   Ticker    │─────────────┘
                    │  (GPS sim)  │
                    └─────────────┘
```

### 1. AVLS (Automatic Vehicle Location System)

- Live map of active vehicles and latest GPS positions
- 30-minute track polylines and historical playback by date
- Depot-scoped access for managers; global view for admin/operators
- Background **ticker** service inserts simulated pings along today's route stops

### 2. Scheduling

- Route CRUD (admin) and weekly duty roster per depot
- Assign drivers to vehicles/routes; publish duties for drivers to acknowledge
- Roster grid: drivers × Mon–Sun with duty status

### 3. Incidents

- Raise and track incidents (P1/P2/P3) with state machine workflow
- Assignment to staff; driver **panic** creates automatic P1 alert
- Event timeline for audit trail

### 4. CMS (Communications)

- Targeted notices (all drivers, depot, or role)
- Read receipts for administrators
- Driver mobile view for unread notices and acknowledgment

## Project layout

```text
backend/          FastAPI app, Alembic migrations, seed data
frontend/         React + Vite UI
tick-script/      GPS simulation worker
docker-compose.yml
.env.example
```

## Development

```bash
# Backend only (requires local Postgres + .env)
cd backend && pip install -r requirements.txt
alembic upgrade head && python -m app.seed
uvicorn app.main:app --reload

# Frontend only
cd frontend && npm install && npm run dev
```

API docs: http://localhost:8000/docs
