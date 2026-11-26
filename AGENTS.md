# AGENTS.md — AI Coding Agent Instructions

This repository implements the **Trento Transit & Study Spot Radar (`v1.0`)**.  
Before writing or modifying any code, read **`README.md`** (architecture, stack, and directory layout) and **`requirements.md`** (`TTSR-SRS-001` formal specification). Those two files are the **Single Source of Truth**.

---

## 1. Mission & Scope Guardrails

1. **Web `v1.0` Only:** Build a mobile-responsive web application (`360px` to `1920px+`). Do **not** scaffold React Native, Expo, Capacitor, or PWA service workers unless explicitly instructed.
2. **Keep It Mobile-Ready:** Follow the three `v1.0` future-proofing rules from `requirements.md`:
   - Prefix all backend endpoints with `/api/v1/`.
   - Enable `GZipMiddleware` in FastAPI.
   - Keep `frontend/src/api/` pure TypeScript (zero React/DOM imports) and send an anonymous `X-Client-ID` UUID header for `POST /api/v1/checkins`.
3. **Business Logic Lives in the Backend:** All spatial queries, Haversine distance calculations, commute-to-seat scoring, and occupancy cascades must execute in `backend/`. Never duplicate ranking or occupancy math in React components.

---

## 2. Authoritative Tech Stack (Do Not Substitute)

### Backend (`backend/`)
* **Runtime & Framework:** Python 3.12+, FastAPI (`0.115+`), Uvicorn, Pydantic v2 + `pydantic-settings`
* **HTTP Client:** `httpx` (`AsyncClient` with HTTP/2 support and `4.0s` upstream timeout)
* **Database:** SQLite 3 + R\*Tree virtual table via `aiosqlite`
* **Caching & Concurrency:** `cachetools` + per-key `asyncio.Lock` (single-flight request coalescing)
* **Scheduling:** `apscheduler` (`3.x` `AsyncIOScheduler`) inside FastAPI lifespan
* **Testing & Linting:** `pytest`, `pytest-asyncio`, `respx`, `ruff`

### Frontend (`frontend/`)
* **Language & Build:** TypeScript (`5.x`, strict mode), React 19, Vite 6
* **State & Fetching:** TanStack Query v5 (`@tanstack/react-query`)
* **Styling:** Tailwind CSS v4
* **Maps:** Leaflet (`leaflet`, `react-leaflet`, `leaflet.markercluster`) + OpenStreetMap tiles
* **Testing & Linting:** `vitest`, `@testing-library/react`, `eslint`

### Infrastructure
* **Containers:** `docker-compose.yml` (`backend` + `frontend` Nginx static server with `/api` reverse proxy and persistent SQLite volume).

---

## 3. Target Repository Layout

Adhere strictly to this directory structure when creating files:

```text
.
├── AGENTS.md
├── README.md
├── requirements.md
├── .env.example
├── .gitignore
├── docker-compose.yml
├── backend/
│   ├── app/
│   │   ├── adapters/
│   │   │   └── trentino_trasporti.py   # Upstream HTTP client & Pydantic normalizers
│   │   ├── db/
│   │   │   ├── schema.sql              # SQLite tables + transit_stops_rtree
│   │   │   └── repository.py           # Async aiosqlite queries & spatial lookups
│   │   ├── models/
│   │   │   └── schemas.py              # Internal /api/v1/ Pydantic v2 response schemas
│   │   ├── services/
│   │   │   ├── cache.py                # Single-flight TTL cache + stale fallback
│   │   │   ├── occupancy.py            # Live / crowdsourced / heuristic cascade
│   │   │   └── radar.py                # Stop-to-spot proximity & commute ranking
│   │   ├── routers/
│   │   │   ├── radar.py                # GET /api/v1/radar
│   │   │   ├── stops.py                # GET /api/v1/stops/{stop_id}/arrivals & /trips/{trip_id}
│   │   │   ├── spots.py                # GET /api/v1/spots, /spots/{spot_id}, POST /api/v1/checkins
│   │   │   ├── bikesharing.py          # GET /api/v1/bikesharing
│   │   │   └── health.py               # GET /api/v1/health
│   │   ├── config.py                   # BaseSettings reading .env
│   │   └── main.py                     # FastAPI app, GZip, CORS, lifespan scheduler
│   ├── data/
│   │   └── trento_study_spots.json     # Seeded >=10 Trento libraries & study rooms
│   ├── tests/
│   │   ├── fixtures/                   # Recorded/mocked JSON fixtures matching upstream schemas
│   │   ├── test_adapter.py
│   │   ├── test_cache.py
│   │   ├── test_occupancy.py
│   │   └── test_api.py
│   ├── pyproject.toml
│   └── Dockerfile
└── frontend/
    ├── src/
    │   ├── api/                        # Pure TS fetchers & interfaces (zero React imports)
    │   ├── components/
    │   │   ├── RadarMap.tsx
    │   │   ├── SpotList.tsx
    │   │   ├── StopArrivalsDrawer.tsx
    │   │   └── FilterBar.tsx
    │   ├── hooks/
    │   │   └── useRadarData.ts         # TanStack Query polling + geolocation
    │   ├── App.tsx
    │   └── main.tsx
    ├── tests/
    ├── package.json
    ├── vite.config.ts
    └── Dockerfile
```

---

## 4. Non-Negotiable Technical Rules & Upstream Quirks

### 4.1 Security & Privacy Rules
* **NEVER** hardcode upstream Basic Auth credentials (`TT_API_USERNAME`, `TT_API_PASSWORD`) anywhere in source code, `docker-compose.yml`, or test fixtures. Read them exclusively from environment variables via `config.py`.
* **NEVER** call `https://app-tpl.tndigit.it/gtlservice` from `frontend/`. All upstream traffic must route through `backend/app/adapters/trentino_trasporti.py`.
* **NEVER** log or persist user origin coordinates (`lat`, `lon`) in SQLite or application logs (`NFR-SEC-02`).
* Hash `X-Client-ID` (or fallback client IP) with a server salt using SHA-256 before storing `occupancy_reports.client_hash` (`NFR-SEC-03`).

### 4.2 Upstream API Quirks (`app-tpl.tndigit.it/gtlservice`)
Every AI agent editing `trentino_trasporti.py` or fixtures must enforce these exact rules from `requirements.md` §3.1:
1. **Headers:** Send HTTP Basic Auth + `X-Requested-With: it.tndigit.mit` (configurable via `TT_API_REQUESTED_WITH`).
2. **`/trips_new` double limit:** The upstream endpoint returns **`2 * limit`** trips. Parse all items, sort chronologically by effective arrival time (falling back to scheduled), filter out trips departed `> 60s` ago, and slice strictly to `limit` (`FR-DEP-02`).
3. **Mixed timezones:** `oraArrivoProgrammataAFermataSelezionata` and `oraArrivoEffettivaAFermataSelezionata` are UTC ISO timestamps (`Z`), whereas `stopTimes[].arrivalTime` / `departureTime` are local `Europe/Rome` `HH:MM:SS` strings. Normalize all exposed API timestamps consistently (`FR-DEP-04`).
4. **Nullable telemetry & field spelling:** `delay`, `matricolaBus`, `lastEventRecivedAt` (note upstream typo `Recived`), and `routeColor` can be `null`. Set `is_realtime = (delay is not None or lastEventRecivedAt is not None)`.
5. **Route colors:** `routeColor` omits the leading `#` and may be `null`. Normalize to `#RRGGBB` or assign a fallback color by `routeType` (`2` rail, `3` bus, `5` cableway).
6. **`.NET` alert dates:** `news[].startDate` and `news[].endDate` use `/Date(<unix_seconds>)/`. Parse the integer seconds into UTC ISO 8601 and discard expired notices (`FR-ING-03`).
7. **Bike-sharing coords:** `/poi/bikesharing` returns `position: [lat, lon]`. Transform to `{ "lat": ..., "lon": ... }`.

### 4.3 Caching & Resilience Rules
* **Single-Flight Coalescing (`NFR-REL-01`):** Concurrent requests for the same `(stop_id, type)` must acquire a per-key `asyncio.Lock` and share one upstream `httpx` call.
* **TTLs:** `/trips_new` = `30s` (configurable via `TT_TRIPS_CACHE_TTL_SECONDS`), `/poi/bikesharing` = `60s`, `/routes` (for `news` alerts) = `15m`, `/stops` = `12h`.
* **Stale Fallback (`NFR-REL-02`):** On upstream timeout (`4.0s`), HTTP `4xx/5xx`, or validation error, return the last cached payload with `stale: true` (never crash with `500` if cached/static data exists).
* **Atomic Sync (`NFR-REL-03`):** Never wipe `transit_stops` or `transit_routes` if the upstream sync fails or returns an empty list.

---

## 5. Phased Implementation Plan (Execute in Order)

When building the project from scratch, complete and verify each phase before moving to the next:

### Phase 1 — Scaffolding & Configuration
* Create `.gitignore`, `.env.example` (matching `README.md` §10.2), `backend/pyproject.toml`, `frontend/package.json`, and `docker-compose.yml`.
* Implement `backend/app/config.py` using `pydantic-settings`.

### Phase 2 — Database Schema & Upstream Transit Adapter
* Implement `backend/app/db/schema.sql` (SQLite tables + `transit_stops_rtree` virtual table) and `repository.py`.
* Implement `backend/app/adapters/trentino_trasporti.py` and Pydantic v2 models covering `/stops`, `/routes`, `/trips_new`, `/trips/{tripId}`, and `/poi/bikesharing`.
* Write fixture-backed `pytest` + `respx` tests in `tests/test_adapter.py` covering every upstream quirk in §4.2.

### Phase 3 — Cache, Study Spots & Occupancy Engine
* Implement `backend/app/services/cache.py` (single-flight TTL cache with stale fallback) + `tests/test_cache.py`.
* Create `backend/data/trento_study_spots.json` with at least 10 real Trento venues (e.g., *Biblioteca Universitaria Centrale (BUC)*, *Biblioteca Comunale di Trento*, *Polo di Povo 0/1/2*, *Mesiano Library*, *Palazzo Prodi*, *Economia Library*, *Sociologia Library*, etc.) with realistic `Europe/Rome` opening hours, coordinates, capacity tiers, and amenities.
* Implement Haversine `spot_stop_links` pre-computation (500m radius, `4.8 km/h` walk speed) and `backend/app/services/occupancy.py` (3-tier cascade, 45-minute half-life decay, 15-minute check-in rate limit).

### Phase 4 — Backend API & Radar Ranking
* Implement `backend/app/services/radar.py` (R\*Tree bounding-box lookup + composite score combining commute time and seat availability + `accessible` filtering).
* Implement all routers under `backend/app/routers/` (`/api/v1/radar`, `/stops`, `/spots`, `/checkins`, `/bikesharing`, `/health`).
* Wire `GZipMiddleware`, `CORSMiddleware`, and APScheduler in `main.py`.
* Verify full backend test suite passes offline using `respx` fixtures.

### Phase 5 — React + Leaflet Frontend Dashboard
* Implement `frontend/src/api/` (typed API client, `X-Client-ID` localStorage UUID helper, zero React imports).
* Implement `useRadarData.ts` using TanStack Query (`refetchInterval: 30_000`, `refetchIntervalInBackground: false`, geolocation defaulting to `46.0679, 11.1211`).
* Build `RadarMap.tsx` (draggable origin marker, color-coded spot markers, clustered stops, bike-sharing toggle), `SpotList.tsx`, `StopArrivalsDrawer.tsx` (countdowns, delay badges, service `news` alerts), and `FilterBar.tsx`.
* Ensure mobile bottom-sheet responsiveness down to `360px` width, WCAG 2.1 AA contrast, icon+text+color badges (`NFR-USA-01`), and `"Last updated"` / `Stale` / `Estimated` indicators (`FR-UI-04`).
* Write Vitest unit tests for API normalization, filtering, and check-in states.

### Phase 6 — Integration & Container Verification
* Run `vite build` and verify initial JS bundle (excluding tiles) stays `<= 250 KB` gzipped (`NFR-PERF-03`).
* Verify `docker compose build` and `docker compose up` start cleanly with `/api/v1/health` returning `200 OK`.

---

## 6. Verification Commands

Agents must run the relevant checks after making changes and report the actual results:

```bash
# Backend lint & tests (must run offline via respx fixtures)
cd backend
ruff check app tests
pytest -v

# Frontend lint, tests & production bundle check
cd frontend
npm run lint
npm test -- --run
npm run build

# Full stack container smoke test
docker compose up --build -d
curl -f http://localhost:8000/api/v1/health
```

---

## 7. Definition of Done Checklist

Before considering a task or milestone complete, verify:
- [ ] All unit/integration tests pass without making live network calls to `app-tpl.tndigit.it`.
- [ ] No credentials, secrets, or user coordinates are hardcoded or logged.
- [ ] Upstream quirks (`2 * limit`, `/Date(...)/`, nullable fields, UTC vs local `stopTimes`, `[lat, lon]` bike-share) are handled and covered by tests.
- [ ] Simulated upstream failure (`503` or timeout) returns cached `stale: true` data gracefully.
- [ ] Responsive layout works cleanly at `360x800` (no horizontal overflow) and `1440x900`.