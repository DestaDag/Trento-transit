# Trento Transit & Study Spot Radar

> **Document Type:** Formal Software Project Proposal, Architecture & Requirements Specification (SRS)  
> **Target Region:** Trento, Italy  
> **Upstream Transit Reference:** [`matteocontrini/trentino-trasporti-api`](https://github.com/matteocontrini/trentino-trasporti-api)  
> **Status:** Foundation Specification (v1.0)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement & Objectives](#2-problem-statement--objectives)
3. [Project Scope](#3-project-scope)
4. [Target Users & Personas](#4-target-users--personas)
5. [Definitive Technology Stack](#5-definitive-technology-stack)
6. [System Architecture & Upstream API Integration](#6-system-architecture--upstream-api-integration)
7. [Functional Requirements](#7-functional-requirements)
8. [Non-Functional Requirements](#8-non-functional-requirements)
9. [Conceptual Data Model & Core API Endpoints](#9-conceptual-data-model--core-api-endpoints)
10. [Repository Structure & Configuration](#10-repository-structure--configuration)
11. [Risks & Mitigations](#11-risks--mitigations)
12. [Implementation Roadmap](#12-implementation-roadmap)
13. [Acceptance Criteria](#13-acceptance-criteria)

---

## 1. Executive Summary

The **Trento Transit & Study Spot Radar** is a lightweight, responsive web dashboard engineered for daily urban utility in Trento. It merges real-time public transit departures and service disruptions—sourced from Trentino Trasporti's API as documented in [`matteocontrini/trentino-trasporti-api`](https://github.com/matteocontrini/trentino-trasporti-api)—with live or estimated library and study room seating availability on an interactive map.

Using a local spatial database, short-TTL server-side caching, and asynchronous frontend polling, the dashboard eliminates fragmented lookups and answers a single actionable question in seconds:

> *"Where can I find an available study seat right now, and when is the next bus, train, or bike-share to get me there?"*

---

## 2. Problem Statement & Objectives

### 2.1 Problem Statement
* **Fragmented Tools:** Students and remote workers must manually cross-reference transit apps against university or municipal library hours before commuting between central Trento and hillside campuses (e.g., Povo and Mesiano).
* **Peak-Hour Saturation:** During exam sessions or bad weather, popular venues fill quickly, resulting in wasted transit commutes when users arrive at full capacity.
* **Heavyweight Interfaces:** Standard mobility apps prioritize multi-step trip planning and ticketing rather than glanceable, destination-capacity-aware decision-making.

### 2.2 Project Objectives
1. **Reliable Upstream Proxying:** Integrate Trentino Trasporti's `/stops`, `/routes`, `/trips_new`, and `/poi/bikesharing` endpoints behind a dedicated FastAPI proxy with HTTP Basic auth handling, response normalization, and TTL caching.
2. **Unified Spatial Radar:** Display transit stops, active route alerts, bike-sharing stations, and study spots on an interactive map paired with a commute-aware ranked list.
3. **Transparent Occupancy Estimation:** Provide real-time or estimated study spot occupancy via a clear fallback cascade (official feed -> crowdsourced check-ins -> time-based heuristics).
4. **Resilient Daily Utility:** Guarantee fast load times, mobile responsiveness, and graceful degradation when upstream transit feeds experience latency or downtime.

---

## 3. Project Scope

### 3.1 In-Scope (v1.0)
* **Backend Transit Adapter & Cache:** Periodic sync of urban/extra-urban stops and Trento-area routes (`areaId` `23` for Urbano Trento, `7` for rail, `8` for funivia), plus short-TTL cached queries for upcoming departures and real-time delays via `/trips_new`.
* **Multi-Modal Bonus Layer:** Optional map toggle for live Trento bike-sharing station availability (`bikes` / `slots`) via `/poi/bikesharing`.
* **Study Spot Directory & Occupancy Engine:** Curated dataset of Trento libraries and study halls (opening hours, capacity tiers, amenities) combined with heuristic models and anonymous rate-limited user check-ins.
* **Interactive Dashboard:** Map-and-list UI with origin pinning, amenity/commute filtering, live departure countdowns, service disruption badges (`news` alerts), and accessibility filtering (`wheelchairBoarding` / `wheelchairAccessible`).

### 3.2 Out-of-Scope (v1.0)
* Public transit ticket purchasing or fare calculation.
* Turn-by-turn GPS navigation.
* Institutional desk-booking integrations.
* User accounts, authentication, or persistent user location tracking.

---

## 4. Target Users & Personas

| Persona | Profile | Primary Use Case |
| :--- | :--- | :--- |
| **Commuter Student** | Travels between central Trento (e.g., Piazza Dante) and Povo/Mesiano campuses. | Checks next Line 5 / Line 13 departures and delays alongside current seating availability before heading to a stop. |
| **Exam-Session Student** | Needs a quiet desk with power outlets during peak afternoon hours. | Filters venues by `Quiet Zone + Outlets` and sorts by lowest occupancy and shortest total commute time. |
| **Remote Worker / Resident** | Seeks an open municipal library or study room between appointments. | Uses geolocation to find an open, uncrowded study spot reachable within 15 minutes by bus or bike-share. |

---

## 5. Definitive Technology Stack

The project standardizes on a cohesive, lightweight, open-source stack optimized for async I/O, zero-ops local spatial caching, and fast client rendering:

| Layer | Technology | Version / Spec | Justification |
| :--- | :--- | :--- | :--- |
| **Backend Runtime & API** | **Python + FastAPI** | Python 3.12, FastAPI 0.115+ | High-performance async REST framework with automatic OpenAPI docs and Pydantic v2 validation to normalize inconsistent upstream fields. |
| **Upstream HTTP Client** | **`httpx` (Async)** | `httpx` 0.27+ | Native async HTTP/2 client for authenticated Basic Auth requests to `app-tpl.tndigit.it/gtlservice` with strict timeouts and connection pooling. |
| **Database & Spatial Cache** | **SQLite 3 + R\*Tree (`aiosqlite`)** | SQLite 3.45+ | Zero-ops embedded storage for synced stops, routes, study spots, and check-ins with R\*Tree bounding-box spatial indexing. |
| **Hot Cache & Coalescing** | **In-Memory Async TTL Cache (`cachetools` + `asyncio.Lock`)** | In-process | Per-stop single-flight request coalescing and 30–60s TTL caching for `/trips_new` and `/poi/bikesharing` to protect the upstream server. |
| **Background Scheduler** | **APScheduler / Asyncio Tasks** | `apscheduler` 3.x | Periodically refreshes static `/stops`, `/routes` (including `news` alerts), and cleans expired check-in entries. |
| **Frontend Framework** | **TypeScript + React + Vite** | TS 5.x, React 19, Vite 6 | Strict type safety shared across API contracts, fast HMR, and minimal production bundle size. |
| **Async Client State** | **TanStack Query (React Query)** | v5 | Built-in stale-while-revalidate caching, background polling (`refetchInterval`), and offline/error state tracking. |
| **UI Styling** | **Tailwind CSS** | v4 | Rapid utility-first styling for responsive desktop split-view and mobile bottom-sheet layouts. |
| **Interactive Mapping** | **Leaflet (`react-leaflet`) + OpenStreetMap** | Leaflet 1.9+ | Lightweight raster map rendering with custom status markers and `leaflet.markercluster` for dense stop clusters. |
| **Testing** | **`pytest` + `respx` / Vitest** | — | `respx` mocks `httpx` calls against recorded Trentino Trasporti JSON fixtures; Vitest covers UI state and filters. |
| **Containerization** | **Docker & Docker Compose** | — | Reproducible two-service setup (`backend` + `frontend` / Nginx static serve) with persistent SQLite volume. |

---

## 6. System Architecture & Upstream API Integration

### 6.1 Component Architecture

```text
+-------------------------------------------------------------------------+
|                    Frontend Dashboard (React + Vite)                    |
|  Leaflet Map (Spots, Stops, Bike-Share) <--> Ranked Spot Cards & Filter |
|  TanStack Query (30-60s background polling, stale-while-revalidate)     |
+------------------------------------+------------------------------------+
                                     | HTTPS / JSON (/api/*)
+------------------------------------v------------------------------------+
|                      Backend API (FastAPI + httpx)                      |
|  - /api/radar          : Spatial search & commute-to-seat ranker        |
|  - /api/stops/:id      : Coalesced & cached upcoming departures         |
|  - /api/spots          : Study spot details, hours & occupancy resolver |
|  - /api/checkins       : Rate-limited anonymous occupancy reports       |
|  - /api/bikesharing    : Cached bike-sharing availability               |
+------------------+----------------------------------+-------------------+
                   |                                  |
+------------------v------------------+   +-----------v-------------------+
|    Local Storage & Cache Layer      |   |  Upstream Trentino Trasporti  |
|  - SQLite + R*Tree (Stops, Routes,  |   |  app-tpl.tndigit.it/gtlservice|
|    Venues, Proximity Links, Alerts) |   |  (Basic Auth + Mobile Headers)|
|  - In-Memory Single-Flight TTL Cache|   |  /stops, /routes, /trips_new, |
+-------------------------------------+   |  /poi/bikesharing             |
                                          +-------------------------------+
```

### 6.2 Upstream Integration Details (`trentino-trasporti-api`)
Per the specification in [`matteocontrini/trentino-trasporti-api`](https://github.com/matteocontrini/trentino-trasporti-api), the backend adapter integrates with `https://app-tpl.tndigit.it/gtlservice` using HTTP Basic Auth and mobile client headers (`X-Requested-With: it.tndigit.mit`) injected via environment variables:

1. **Static & Alert Sync (Periodic — e.g., every 6–12 hours for stops, 15 minutes for route alerts):**
   * `GET /stops` (filtered by `type=U` and `type=E`): Populates local SQLite `transit_stops` with `stopId`, `stopCode`, `stopName`, `stopLat`, `stopLon`, `wheelchairBoarding`, and linked `routes`.
   * `GET /routes?areas=23,7,8`: Syncs Trento urban bus routes (`23`), regional/local rail (`7`), and the Trento–Sardagna cableway (`8`), extracting `routeColor` and active service disruption notices (`news[]`).
2. **Real-Time Departures (On-demand with 30–45s TTL cache + single-flight lock):**
   * `GET /trips_new?stopId={id}&type={U|E}&limit={n}&refDateTime={iso}`: Fetches upcoming trips for a stop. The adapter normalizes `oraArrivoProgrammataAFermataSelezionata`, `oraArrivoEffettivaAFermataSelezionata`, `delay` (minutes), `tripHeadsign`, `wheelchairAccessible`, and accounts for the upstream behavior where `trips_new` returns double the requested `limit`.
3. **Bike Sharing (On-demand with 60s TTL cache):**
   * `GET /poi/bikesharing`: Surfaces available `bikes` and free `slots` across Trento stations.

### 6.3 Study Spot Occupancy Cascade
Since study venues rarely publish open live sensor feeds, occupancy is resolved through a prioritized cascade:
1. **Official Live Feed** *(extensible adapter hook if a venue provides a public API)*.
2. **Crowdsourced Check-In Signal** *(recent anonymous user reports decayed exponentially over 45–60 minutes)*.
3. **Heuristic Baseline Model** *(day-of-week, hour-of-day, and academic exam-period curves)*.

Every API response explicitly labels the active source (`live`, `crowdsourced`, or `estimated`).

---

## 7. Functional Requirements

### 7.1 Transit Integration & Normalization
* **FR-01 (Stop & Route Ingestion):** The backend shall periodically fetch `/stops` and `/routes?areas=23,7,8` from `app-tpl.tndigit.it/gtlservice` and persist them in SQLite with R\*Tree spatial indexing.
* **FR-02 (Next Departures Proxy):** Given a `stopId` and current `Europe/Rome` timestamp, `/api/stops/{id}/arrivals` shall return the next $N$ (default 5) departures by querying `/trips_new`, normalizing scheduled time, effective time, delay offset, route color, and accessibility flags.
* **FR-03 (Service Alert Surfacing):** Route-level `news` notices returned by `/routes` (parsing `.NET` `/Date(epoch)/` strings into ISO 8601) shall be attached to affected transit stops and study-spot commute cards.
* **FR-04 (Multi-Modal Bike Sharing):** The backend shall expose `/api/bikesharing` by caching `/poi/bikesharing` responses so users can view nearby bike availability alongside bus stops.

### 7.2 Study Spot & Occupancy Management
* **FR-05 (Curated Venue Directory):** The system shall store each Trento study venue's coordinates, address, opening hours, special holiday closures, capacity tier, and amenities (`wifi`, `outlets`, `quiet_zone`, `accessible`).
* **FR-06 (Stop-to-Venue Linking):** On startup/sync, the system shall pre-compute the nearest transit stops (within 500m) and estimated walking durations for every study spot.
* **FR-07 (Availability Classification):** Open spots shall be classified as `Available` (<50% occupancy), `Moderate` (50–80%), `Busy` (>80%), or `Closed`.
* **FR-08 (Anonymous Crowdsourced Check-Ins):** Users shall be able to submit a rate-limited, anonymous occupancy report (`Plenty of seats`, `Half full`, `Almost full`) via `POST /api/checkins`.

### 7.3 Radar Dashboard & Spatial Search
* **FR-09 (Origin Selection):** The UI shall request browser geolocation (defaulting gracefully to Piazza Duomo / Trento Station `46.0679, 11.1211`) and allow dragging or clicking the map to set a custom origin.
* **FR-10 (Interactive Map):** Leaflet shall render color-coded study spot markers (by occupancy), clustered transit stops, and optional bike-sharing markers. Clicking a study spot shall highlight its linked stops and fetch live departures.
* **FR-11 (Commute-Aware Ranking):** `/api/radar` shall rank open spots using a composite score combining estimated commute time (walk to origin stop + next transit wait/ride + walk to venue) and seat availability.
* **FR-12 (Filtering):** Users shall be able to filter by `Open Now`, minimum seat availability, `Wheelchair Accessible` (matching `wheelchairBoarding` / `wheelchairAccessible`), and required venue amenities.

### 7.4 Caching & Asynchronous UX
* **FR-13 (Non-Disruptive Polling):** TanStack Query shall poll active departure and radar data every 30–60 seconds without resetting map pan, zoom, or active filters.
* **FR-14 (Freshness & Fallback Indicators):** The UI shall display a `"Last updated"` timestamp and clearly indicate when transit data is served from stale cache or when occupancy is `Estimated`.

---

## 8. Non-Functional Requirements

### 8.1 Performance
* **NFR-01 (API Latency):** Cached `/api/radar` queries shall respond in $\le 200\text{ ms}$ (p95) using SQLite R\*Tree spatial indexing.
* **NFR-02 (Frontend Bundle):** Initial production JS bundle (excluding map tiles) shall remain $\le 250\text{ KB}$ gzipped.

### 8.2 Upstream Stewardship & Reliability
* **NFR-03 (Single-Flight & Rate Protection):** The backend shall enforce per-stop `asyncio.Lock` request coalescing and a minimum 30s TTL cache so concurrent users never trigger duplicate upstream `/trips_new` calls.
* **NFR-04 (Graceful Degradation):** Upstream timeouts (>4s) or HTTP 5xx errors from `app-tpl.tndigit.it` shall not crash the application; the backend shall return the last cached payload marked `stale: true` or degrade gracefully to static stop/venue data.

### 8.3 Usability, Accessibility & Privacy
* **NFR-05 (Responsive Layout):** The UI shall adapt cleanly across desktop split-view and mobile bottom-sheet layouts down to `360px` width.
* **NFR-06 (WCAG 2.1 AA):** Occupancy indicators shall pair color with text labels and icons rather than relying on color alone.
* **NFR-07 (Location Privacy):** User coordinates shall only be used transiently for spatial queries and never logged persistently.
* **NFR-08 (Check-In Abuse Prevention):** `POST /api/checkins` shall enforce IP-hash rate limiting (e.g., max 1 report per venue per 15 minutes per client) and median/decay smoothing.

---

## 9. Conceptual Data Model & Core API Endpoints

### 9.1 SQLite Core Entities
* **`transit_stops`**: `stop_id`, `stop_code`, `stop_name`, `stop_type` (`U`/`E`), `lat`, `lon`, `wheelchair_boarding`, `routes_json`, `updated_at`
* **`transit_routes`**: `route_id`, `short_name`, `long_name`, `area_id`, `route_type`, `color_hex`, `news_json`, `updated_at`
* **`study_spots`**: `spot_id`, `name`, `address`, `lat`, `lon`, `hours_json`, `capacity_tier`, `amenities_json`
* **`spot_stop_links`**: `spot_id`, `stop_id`, `walk_distance_m`, `walk_minutes`
* **`occupancy_reports`**: `id`, `spot_id`, `level` (`1..3`), `client_hash`, `created_at`

### 9.2 Backend REST API Summary

| Method & Path | Description | Cache Policy |
| :--- | :--- | :--- |
| `GET /api/radar?lat=&lon=&radius=&filters=` | Returns nearby study spots ranked by commute + seat availability, plus linked stops and alerts. | Spatial SQLite + cached stop arrivals |
| `GET /api/stops/{stop_id}/arrivals?type=U` | Proxies and normalizes `/trips_new` for upcoming bus/train departures and delays. | 30s TTL + single-flight lock |
| `GET /api/spots` | Lists all Trento study spots with current occupancy status and source badge. | In-memory 30s |
| `POST /api/checkins` | Submits an anonymous, rate-limited occupancy report for a study spot. | Immediate write + invalidates spot score |
| `GET /api/bikesharing` | Proxies `/poi/bikesharing` for live bike & dock counts. | 60s TTL |
| `GET /api/health` | Reports backend DB health and upstream Trentino Trasporti reachability. | Uncached |

---

## 10. Repository Structure & Configuration

### 10.1 Project Directory Layout

```text
trento-transit-study-radar/
├── backend/
│   ├── app/
│   │   ├── adapters/
│   │   │   └── trentino_trasporti.py   # Async httpx client for app-tpl.tndigit.it/gtlservice
│   │   ├── db/
│   │   │   ├── schema.sql              # SQLite tables + R*Tree virtual index
│   │   │   └── repository.py           # aiosqlite queries
│   │   ├── services/
│   │   │   ├── cache.py                # Single-flight TTL cache
│   │   │   ├── occupancy.py            # Live / crowdsourced / heuristic engine
│   │   │   └── radar.py                # Proximity & commute-to-seat ranking
│   │   ├── routers/
│   │   │   ├── radar.py
│   │   │   ├── stops.py
│   │   │   ├── spots.py
│   │   │   └── bikesharing.py
│   │   ├── config.py                   # Pydantic Settings (.env)
│   │   └── main.py                     # FastAPI entrypoint & lifespan scheduler
│   ├── data/
│   │   └── trento_study_spots.json     # Seeded Trento libraries & campus study rooms
│   ├── tests/
│   │   ├── fixtures/                   # Sample JSON responses from Trentino Trasporti
│   │   └── test_adapter.py
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/                        # Typed fetchers & Zod/TS response interfaces
│   │   ├── components/
│   │   │   ├── RadarMap.tsx            # Leaflet map, markers & clusters
│   │   │   ├── SpotList.tsx            # Ranked study spot cards
│   │   │   ├── StopArrivalsDrawer.tsx  # Live countdowns & delay badges
│   │   │   └── FilterBar.tsx           # Amenities, accessibility & availability filters
│   │   ├── hooks/
│   │   │   └── useRadarData.ts         # TanStack Query polling + geolocation
│   │   └── App.tsx
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

### 10.2 Environment Configuration (`.env.example`)
Credentials and upstream parameters for `trentino-trasporti-api` must be injected via environment variables rather than hardcoded in source files:

```ini
TT_API_BASE_URL=https://app-tpl.tndigit.it/gtlservice
TT_API_USERNAME=
TT_API_PASSWORD=
TT_API_REQUESTED_WITH=it.tndigit.mit
TT_TRENTO_AREAS=23,7,8
TT_TRIPS_CACHE_TTL_SECONDS=30
SQLITE_DB_PATH=./data/radar.db
CHECKIN_RATE_LIMIT_SECONDS=900
```

---

## 11. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
| :--- | :---: | :---: | :--- |
| **Upstream reverse-engineered API (`app-tpl.tndigit.it`) changes, rate-limits, or rotates Basic Auth credentials** | Medium | High | Isolate all upstream calls in `trentino_trasporti.py`; inject credentials via `.env`; enforce single-flight TTL caching; fall back cleanly to cached stop/schedule data. |
| **Upstream response quirks** (e.g., `/trips_new` returning double `limit`, `/Date(...)/` timestamps in `news`, nullable `delay`) | High | Medium | Validate and normalize all upstream payloads through strict Pydantic v2 models with fixture-backed unit tests. |
| **Absence of live library seat sensors** | High | Medium | Use transparent time-of-day/academic-calendar heuristic curves paired with rate-limited crowdsourced check-ins and explicit source badges. |
| **OSM tile rate-limiting in production** | Low | Medium | Configure tile URL via frontend env variable to support caching proxies or commercial free-tier vector/raster providers if traffic grows. |

---

## 12. Implementation Roadmap

* **Milestone 1 — Backend Foundation & Transit Adapter (Weeks 1–2):**  
  Set up FastAPI, SQLite R\*Tree schema, `httpx` client for `/stops`, `/routes`, `/trips_new`, and `/poi/bikesharing`, single-flight TTL cache, and `respx` unit tests.
* **Milestone 2 — Study Spot Directory & Occupancy Engine (Weeks 3–4):**  
  Author `trento_study_spots.json` (e.g., BUC, Biblioteca Comunale, Povo/Mesiano study halls), pre-compute stop links, implement heuristic curves, and build `POST /api/checkins`.
* **Milestone 3 — Radar & Ranking API (Week 5):**  
  Implement `/api/radar` composite scoring (walk + transit wait + occupancy), accessibility filtering, and service alert attachment.
* **Milestone 4 — React + Leaflet Dashboard (Weeks 6–7):**  
  Build interactive map, marker clustering, ranked card list, TanStack Query 30s polling, staleness indicators, and mobile bottom-sheet UX.
* **Milestone 5 — QA, Dockerization & Release (Week 8):**  
  Containerize with Docker Compose, run upstream-failure resilience tests, verify WCAG contrast and `360px` responsiveness, and tag `v1.0.0`.

---

## 13. Acceptance Criteria

The `v1.0` release is complete when:
1. `/stops`, `/routes`, `/trips_new`, and `/poi/bikesharing` sync and resolve accurately via the FastAPI adapter using environment-injected credentials and verified single-flight TTL caching.
2. At least 10 Trento study venues are seeded with accurate hours, nearest transit stops, walking estimates, and source-labeled occupancy states (`Live`, `Crowdsourced`, or `Estimated`).
3. Simulating an upstream timeout or HTTP 500 from `app-tpl.tndigit.it` degrades gracefully to cached/static data without crashing the backend or UI.
4. Cached `/api/radar` responses execute in $\le 200\text{ ms}$ (p95) and the frontend passes mobile layout checks (`360px`+) and WCAG 2.1 AA contrast validation.