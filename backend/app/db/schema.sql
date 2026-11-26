CREATE TABLE IF NOT EXISTS transit_stops (
    stop_id TEXT PRIMARY KEY,
    stop_code TEXT,
    stop_name TEXT NOT NULL,
    stop_type TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    wheelchair_boarding INTEGER DEFAULT 0,
    routes_json TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS transit_stops_rtree USING rtree(
    id, min_lat, max_lat, min_lon, max_lon
);

CREATE TABLE IF NOT EXISTS transit_routes (
    route_id TEXT PRIMARY KEY,
    area_id TEXT,
    short_name TEXT,
    long_name TEXT,
    route_type INTEGER,
    color_hex TEXT,
    news_json TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS study_spots (
    spot_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    address TEXT,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    hours_json TEXT NOT NULL DEFAULT '{}',
    holidays_json TEXT NOT NULL DEFAULT '{}',
    capacity_tier TEXT NOT NULL,
    amenities_json TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS spot_stop_links (
    spot_id TEXT NOT NULL,
    stop_id TEXT NOT NULL,
    walk_distance_m REAL NOT NULL,
    walk_minutes REAL NOT NULL,
    PRIMARY KEY (spot_id, stop_id)
);

CREATE TABLE IF NOT EXISTS occupancy_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spot_id TEXT NOT NULL,
    level INTEGER NOT NULL CHECK (level BETWEEN 1 AND 3),
    client_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_occupancy_spot_created
ON occupancy_reports (spot_id, created_at);