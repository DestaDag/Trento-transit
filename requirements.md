# Software Requirements Specification (SRS)
## Trento Transit & Study Spot Radar (`v1.0`)

| Metadata | Value |
| :--- | :--- |
| **Document ID** | `TTSR-SRS-001` |
| **Version** | `1.0.0` |
| **Date** | `2026-11-26` |
| **Status** | Approved Baseline (Web `v1.0`) |
| **Target Region** | Trento, Italy (`Europe/Rome`) |
| **Upstream API Reference** | [`matteocontrini/trentino-trasporti-api`](https://github.com/matteocontrini/trentino-trasporti-api) |

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Overall Description & Constraints](#2-overall-description--constraints)
3. [External Interface Requirements](#3-external-interface-requirements)
4. [Functional Requirements](#4-functional-requirements)
5. [Non-Functional Requirements](#5-non-functional-requirements)
6. [Data Requirements & Persistence](#6-data-requirements--persistence)
7. [Verification & Acceptance Matrix](#7-verification--acceptance-matrix)

---

## 1. Introduction

### 1.1 Purpose
This document defines the complete functional, non-functional, data, and external interface requirements for **Trento Transit & Study Spot Radar (`v1.0`)**. It serves as the authoritative engineering specification for backend proxy development, frontend dashboard implementation, automated testing, and acceptance sign-off.

### 1.2 Scope
The `v1.0` system is a responsive **web application** (desktop and mobile browsers down to `360px` width) backed by a **FastAPI** service and **SQLite (R\*Tree)** spatial cache. It unifies:
* Public transit stops, routes, service notices, real-time trip delays, and bike-sharing availability retrieved from Trentino Trasporti's *Muoversi in Trentino* backend (`https://app-tpl.tndigit.it/gtlservice`) as documented in `matteocontrini/trentino-trasporti-api`.
* Curated Trento study venue metadata (libraries, university study halls, opening hours, amenities) paired with a tiered occupancy estimation and crowdsourced check-in engine.

Native mobile applications (iOS/Android) and PWA offline packaging are explicitly deferred to post-`v1.0` releases, though `/api/v1/` API versioning and stateless client tokens are included in `v1.0` to keep the backend mobile-ready.

### 1.3 Definitions & Acronyms
* **Upstream API:** The reverse-engineered Trentino Trasporti REST service hosted at `https://app-tpl.tndigit.it/gtlservice`.
* **Urban (`U`) / Extra-Urban (`E`):** Upstream transit classification where `U` covers urban bus networks and the Trento–Sardagna cableway (*funivia*), and `E` covers provincial bus basins and regional rail (*ferrovia*).
* **Area ID:** Numeric transit basin identifier used by `/routes` (e.g., `23` = Urbano Trento, `7` = Ferrovia, `8` = Funivia).
* **Single-Flight Cache:** Request coalescing mechanism ensuring concurrent requests for the same uncached resource trigger only one upstream HTTP call.
* **TTL:** Time-To-Live for cached entries.

---

## 2. Overall Description & Constraints

### 2.1 Operating Environment
* **Backend:** Python 3.12, FastAPI, `httpx` (async), `aiosqlite` (SQLite 3 + R\*Tree), APScheduler, containerized via Docker.
* **Frontend:** TypeScript, React 19, Vite, Tailwind CSS, TanStack Query v5, Leaflet (`react-leaflet` + `leaflet.markercluster`), served as static assets via Nginx/CDN.
* **Timezone:** All schedule computations and opening-hour evaluations shall operate in `Europe/Rome` (CET/CEST).

### 2.2 Design & Upstream Integration Constraints
1. **Mandatory Backend Proxy:** Because the upstream API requires HTTP Basic authentication and mobile WebView headers (`X-Requested-With: it.tndigit.mit`), browser clients must never call `app-tpl.tndigit.it` directly. All upstream traffic shall pass through the FastAPI adapter to avoid CORS failures and credential exposure.
2. **Environment-Injected Credentials:** Upstream Basic Auth credentials and base URLs documented in `matteocontrini/trentino-trasporti-api` shall be configured strictly via `.env` / runtime environment variables (`TT_API_USERNAME`, `TT_API_PASSWORD`, `TT_API_BASE_URL`) and excluded from version control.
3. **Unofficial Upstream Stability:** Because the upstream API is reverse-engineered from a mobile client rather than a formal public SLA, the system must tolerate schema quirks, nullable telemetry fields, and intermittent outages without failing.

---

## 3. External Interface Requirements

### 3.1 Upstream Trentino Trasporti API (`app-tpl.tndigit.it/gtlservice`)

The backend adapter (`trentino_trasporti.py`) shall interface with the following documented endpoints using HTTP Basic Auth and optional mobile headers (`User-Agent`, `X-Requested-With: it.tndigit.mit`):

| Upstream Endpoint | Query Params | Consumed Fields | Known Upstream Quirks & Normalization Rules |
| :--- | :--- | :--- | :--- |
| **`GET /stops`** | `type=U` or `E`, optional `size` | `stopId`, `stopCode`, `stopName`, `stopDesc`, `stopLat`, `stopLon`, `stopLevel`, `street`, `town`, `type`, `wheelchairBoarding`, `routes[]` | `distance` is `null` when unreferenced; `routes[].routeColor` may be `null`; `wheelchairBoarding` uses numeric codes (`0`, `2`, etc.). |
| **`GET /routes`** | `areas=23,7,8` (comma-separated) | `areaId`, `routeId`, `routeShortName`, `routeLongName`, `routeColor`, `routeType`, `type`, `news[]` | `routeColor` may be `null` and omits leading `#`; `news[].startDate` and `endDate` use `.NET` `/Date(<unix_seconds>)/` strings (e.g., `/Date(1673654400)/`). |
| **`GET /trips_new`** | `stopId` (or `routeId`), `type` (`U`/`E`), `limit`, optional `directionId` (`0`/`1`), `refDateTime` (ISO 8601) | `tripId`, `routeId`, `type`, `directionId`, `tripHeadsign`, `delay`, `lastEventRecivedAt`, `lastSequenceDetection`, `matricolaBus`, `stopLast`, `stopNext`, `oraArrivoProgrammataAFermataSelezionata`, `oraArrivoEffettivaAFermataSelezionata`, `wheelchairAccessible`, `tripFlag`, `stopTimes[]` | Always returns **`2 * limit`** trips; `delay`, `matricolaBus`, and `lastEventRecivedAt` (note upstream spelling `Recived`) are `null` when real-time data is absent; `oraArrivo*` timestamps are UTC (`Z`) while `stopTimes[].arrivalTime` / `departureTime` are local `HH:MM:SS` strings; `oraArrivo*` fields are `null` when querying by `routeId` instead of `stopId`. |
| **`GET /trips/{tripId}`** | Path: `tripId` | Same schema as single item in `/trips_new` | Used for on-demand inspection of a trip's full `stopTimes[]` sequence. |
| **`GET /poi/bikesharing`** | None | `id`, `name`, `address`, `position` (`[lat, lon]`), `bikes`, `slots`, `totalSlots` | `position` is a two-element `[lat, lon]` array rather than named `lat`/`lon` keys. |

*Note: Auxiliary endpoints documented upstream (`GET /poi/contextaware/stazioni` for station accessibility and `GET /direction` for routing) are reserved for post-`v1.0` expansion.*

### 3.2 Internal Backend REST API (`/api/v1/*`)
All internal endpoints shall return JSON (`Content-Type: application/json`), support GZip compression, and expose OpenAPI 3.1 documentation at `/docs`:

* `GET /api/v1/radar?lat={float}&lon={float}&radius_m={int}&open_now={bool}&min_availability={str}&accessible={bool}&amenities={csv}`
* `GET /api/v1/stops/{stop_id}/arrivals?type={U|E}&limit={int}`
* `GET /api/v1/trips/{trip_id}`
* `GET /api/v1/spots` & `GET /api/v1/spots/{spot_id}`
* `POST /api/v1/checkins` (accepts `spot_id`, `level` `1..3`, and optional `X-Client-ID` UUID header)
* `GET /api/v1/bikesharing`
* `GET /api/v1/health`

### 3.3 User Interface
* Desktop viewport (`>= 1024px`): Split-screen layout pairing an interactive Leaflet map with a scrollable, ranked study-spot and departure panel.
* Mobile web viewport (`360px`–`1023px`): Full-screen map with an expandable bottom-sheet list and touch-friendly filter pills.

---

## 4. Functional Requirements

### 4.1 Transit Data Ingestion & Normalization
* **FR-ING-01:** On initial startup (if the SQLite database is empty) and via a scheduled job every 12 hours, the backend shall fetch `GET /stops?type=U` and `GET /stops?type=E`, filter or tag Trento-relevant stops, and upsert them into SQLite with R\*Tree spatial coordinates (`stopLat`, `stopLon`).
* **FR-ING-02:** Every 15 minutes, the backend shall fetch `GET /routes?areas=23,7,8` to refresh Trento urban bus (`23`), rail (`7`), and funivia (`8`) metadata alongside active `news[]` service alerts.
* **FR-ING-03:** The route parser shall convert `.NET` `/Date(<epoch>)/` values inside `news[].startDate` and `news[].endDate` into standard UTC ISO 8601 timestamps and retain only alerts active at the current time.
* **FR-ING-04:** The adapter shall normalize nullable `routeColor` values by prepending `#` to valid 6-digit hex strings and assigning deterministic fallback colors based on `routeType` (`2` rail, `3` bus, `5` cableway) when `null`.

### 4.2 Real-Time Departures & Trip Resolution
* **FR-DEP-01:** When `/api/v1/stops/{stop_id}/arrivals` is called, the backend shall query upstream `GET /trips_new` with `stopId`, `type` (`U` or `E`), `limit`, and current UTC ISO 8601 `refDateTime`.
* **FR-DEP-02:** Because `/trips_new` returns double the requested `limit`, the backend shall parse all returned items, sort chronologically by effective arrival time (falling back to scheduled time), filter out already-departed trips older than 60 seconds, and slice the result strictly to the requested `limit`.
* **FR-DEP-03:** For each trip, the normalized payload shall include `is_realtime: true` when `delay` or `lastEventRecivedAt` is non-null, and `is_realtime: false` (`Scheduled`) otherwise.
* **FR-DEP-04:** All departure timestamps exposed by `/api/v1/` shall be normalized to ISO 8601 with explicit timezone offsets (`Europe/Rome` or UTC `Z`), reconciling UTC `oraArrivo*` fields with local `stopTimes[]` strings.
* **FR-DEP-05:** When a user selects a specific upcoming departure in the UI, `/api/v1/trips/{trip_id}` shall fetch and return the ordered `stopTimes[]` sequence from upstream `GET /trips/{tripId}` (cached for 30s).

### 4.3 Service Alerts & Bike-Sharing
* **FR-ALT-01:** Any active `news[]` alert linked via `routeIds[]` or `stopId` shall be surfaced on affected stop departure drawers and study-spot commute summaries, including `header`, `details`, and external `url`.
* **FR-BIK-01:** `/api/v1/bikesharing` shall proxy upstream `GET /poi/bikesharing`, transforming `position: [lat, lon]` into explicit `lat` and `lon` fields alongside `bikes`, `slots`, and `totalSlots`.

### 4.4 Study Spot Directory & Proximity Linking
* **FR-SPT-01:** The system shall load a curated seed file (`trento_study_spots.json`) containing at least 10 Trento study venues (e.g., BUC, Biblioteca Comunale, Povo and Mesiano campus study areas) with coordinates, opening hours per weekday, holiday overrides, capacity tier, and amenities (`wifi`, `outlets`, `quiet_zone`, `accessible`).
* **FR-SPT-02:** After every stop ingestion sync, the backend shall compute and store `spot_stop_links` for all transit stops within a 500-meter Haversine radius of each study spot, recording walk distance (meters) and estimated walk time (at `4.8 km/h`).

### 4.5 Hybrid Occupancy Engine & Check-Ins
* **FR-OCC-01:** The occupancy service shall resolve each venue's current state using a 3-tier cascade: (1) official live API adapter (if configured), (2) recent crowdsourced check-ins decayed exponentially with a 45-minute half-life, and (3) a day-of-week/hour-of-day heuristic model.
* **FR-OCC-02:** Every spot occupancy object shall classify open venues into `Available` (<50%), `Moderate` (50–80%), or `Busy` (>80%), or `Closed` outside opening hours, and include `source` (`live` | `crowdsourced` | `estimated`).
* **FR-OCC-03:** `POST /api/v1/checkins` shall accept an anonymous occupancy level (`1` = Plenty of seats, `2` = Half full, `3` = Almost full), validate that the venue is currently open, persist the report, and immediately invalidate that spot's cached occupancy score.

### 4.6 Spatial Radar Search & Commute Ranking
* **FR-RAD-01:** `GET /api/v1/radar` shall identify transit stops near the user's origin (`lat`, `lon`) using the SQLite R\*Tree index, fetch cached departures for the top candidate stops linking to open study spots, and compute an estimated end-to-end commute score.
* **FR-RAD-02:** The ranking engine shall sort matching study spots by a composite score combining estimated commute time (walk to origin stop + wait + transit/walk leg + walk from destination stop) and seat availability tier.
* **FR-RAD-03:** Filtering by `accessible=true` shall restrict study spots to `accessible` venues and prioritize transit stops/trips where `wheelchairBoarding > 0` / `wheelchairAccessible == 1`.

### 4.7 Interactive Web Dashboard
* **FR-UI-01:** On load, the frontend shall request browser geolocation (`navigator.geolocation`), falling back automatically to central Trento (`46.0679, 11.1211`) if denied or unavailable, and allow dragging/clicking to relocate the origin pin.
* **FR-UI-02:** The Leaflet map shall render color-coded study spot pins, clustered transit stops, and an optional toggle layer for bike-sharing stations (`bikes` available vs. `slots` free).
* **FR-UI-03:** TanStack Query shall poll `/api/v1/radar` and open stop arrival drawers every 30–60 seconds while paused when the browser tab is hidden (`visibilitychange`), preserving map zoom, center, and active filters.
* **FR-UI-04:** The UI shall display `"Last updated"` timestamps and distinct visual badges when transit data is `Cached / Stale` or when occupancy is `Estimated`.

---

## 5. Non-Functional Requirements

### 5.1 Performance & Caching
* **NFR-PERF-01:** Cached `/api/v1/radar` responses shall execute in $\le 200\text{ ms}$ at the 95th percentile.
* **NFR-PERF-02:** Backend responses shall apply HTTP GZip compression (`GZipMiddleware`) to minimize mobile browser data usage.
* **NFR-PERF-03:** Initial frontend JavaScript bundle size (excluding OSM raster tiles) shall not exceed `250 KB` gzipped.

### 5.2 Upstream Stewardship & Fault Tolerance
* **NFR-REL-01 (Single-Flight Coalescing):** Concurrent requests for the same `stop_id` and `type` shall share a single in-flight `httpx` request protected by a per-key `asyncio.Lock` and cached for a minimum TTL of 30 seconds (`/trips_new`) and 60 seconds (`/poi/bikesharing`).
* **NFR-REL-02 (Timeouts & Graceful Degradation):** Upstream `httpx` requests shall enforce a strict 4-second timeout. On upstream timeout, HTTP 4xx/5xx, or JSON schema failure, the backend shall serve the most recent cached payload flagged `stale: true` (or static stop/venue data if uncached) within `500 ms` rather than returning HTTP 500 to the dashboard.
* **NFR-REL-03 (Atomic Sync Safety):** If a scheduled `/stops` or `/routes` sync fails or returns an empty array, existing SQLite records shall remain untouched.

### 5.3 Security & Privacy
* **NFR-SEC-01:** Upstream Basic Auth credentials (`TT_API_USERNAME`, `TT_API_PASSWORD`) shall never appear in client bundles, logs, or API error traces.
* **NFR-SEC-02:** User origin coordinates (`lat`, `lon`) shall only be processed ephemerally in memory and shall never be persisted to SQLite or application logs.
* **NFR-SEC-03:** `POST /api/v1/checkins` shall enforce rate limiting (maximum 1 submission per `spot_id` every 15 minutes) using a salted SHA-256 hash of `X-Client-ID` (or client IP fallback) to prevent spam while avoiding cellular NAT false positives.

### 5.4 Usability & Accessibility
* **NFR-USA-01:** Every occupancy and delay badge shall meet WCAG 2.1 AA contrast ratios and convey state using both icon/text labels and color.
* **NFR-USA-02:** The layout shall pass responsive usability verification from `360px` width up to `1920px+` without horizontal overflow.

### 5.5 Maintainability & Post-`v1.0` Mobile Readiness
* **NFR-MNT-01:** All backend endpoints shall be versioned under `/api/v1/` and backed by Pydantic v2 response models.
* **NFR-MNT-02:** Frontend API fetchers and TypeScript domain interfaces shall be isolated inside `frontend/src/api/` with zero UI framework coupling so they can be extracted into a shared package for future PWA/mobile clients.

---

## 6. Data Requirements & Persistence

### 6.1 SQLite Schema Requirements
* `transit_stops` + `transit_stops_rtree` (`id`, `min_lat`, `max_lat`, `min_lon`, `max_lon`) for bounding-box spatial lookups.
* `transit_routes` (`route_id`, `area_id`, `short_name`, `long_name`, `route_type`, `color_hex`, `news_json`, `updated_at`).
* `study_spots` (`spot_id`, `name`, `address`, `lat`, `lon`, `hours_json`, `holidays_json`, `capacity_tier`, `amenities_json`).
* `spot_stop_links` (`spot_id`, `stop_id`, `walk_distance_m`, `walk_minutes`).
* `occupancy_reports` (`id`, `spot_id`, `level`, `client_hash`, `created_at`), pruned automatically after 24 hours.

### 6.2 Backup & Reproducibility
* A single `docker compose up` command shall initialize the SQLite schema, seed `trento_study_spots.json`, run initial stop/route ingestion (or load a local snapshot fixture in offline/test mode), and start both services.

---

## 7. Verification & Acceptance Matrix

| Requirement Group | Verification Method | Acceptance Threshold |
| :--- | :--- | :--- |
| **Upstream Adapter (`FR-ING-*`, `FR-DEP-*`, `FR-BIK-*`)** | `pytest` + `respx` mocking recorded JSON fixtures from `trentino-trasporti-api` | Correctly slices `2 * limit` `/trips_new` responses, parses `/Date(...)/` alerts, converts `position[]` bike-share coords, and handles `null` `delay`/`routeColor`. |
| **Coalescing & Fallback (`NFR-REL-01`, `NFR-REL-02`)** | Concurrent async load test (20 parallel requests to same `stop_id`) + simulated upstream 503/timeout | Exactly 1 upstream HTTP call fired within TTL window; simulated failure returns `200 OK` with `stale: true` in `< 500 ms`. |
| **Spatial Radar (`FR-RAD-*`, `NFR-PERF-01`)** | Benchmark test against seeded Trento stops & >=10 venues | `/api/v1/radar` p95 latency $\le 200\text{ ms}$; accurate ranking and `accessible` filtering. |
| **Check-In Engine (`FR-OCC-*`, `NFR-SEC-03`)** | Integration tests against `POST /api/v1/checkins` | Duplicate check-in within 15 min returns `429 Too Many Requests`; valid check-in updates spot state to `crowdsourced`. |
| **Web UI & Accessibility (`FR-UI-*`, `NFR-USA-*`)** | Vitest unit tests + Playwright/DevTools checks at `360x800` & `1440x900` + Lighthouse/axe | Zero console errors, no horizontal scroll at `360px`, WCAG AA contrast pass, bundle $\le 250\text{ KB}$ gzipped. |