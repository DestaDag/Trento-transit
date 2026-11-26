import type {
  ArrivalsResponse,
  BikeSharingResponse,
  CheckinResponse,
  RadarFilters,
  RadarResponse,
  TripDetail,
} from "./types";

const CLIENT_ID_STORAGE_KEY = "trento_radar_client_id";

export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

function generateUuid(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = Math.floor(Math.random() * 16);
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function getOrCreateClientId(storage?: StorageLike): string {
  const store =
    storage ??
    (typeof globalThis !== "undefined" && "localStorage" in globalThis
      ? (globalThis.localStorage as StorageLike)
      : undefined);

  if (!store) {
    return generateUuid();
  }
  const existing = store.getItem(CLIENT_ID_STORAGE_KEY);
  if (existing) {
    return existing;
  }
  const created = generateUuid();
  store.setItem(CLIENT_ID_STORAGE_KEY, created);
  return created;
}

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) {
        detail = body.detail;
      }
    } catch {
      // ignore non-JSON error body
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

export async function fetchRadar(
  lat: number,
  lon: number,
  filters: RadarFilters,
  radiusM = 5000,
): Promise<RadarResponse> {
  const params = new URLSearchParams({
    lat: lat.toFixed(6),
    lon: lon.toFixed(6),
    radius_m: String(radiusM),
    open_now: String(filters.openNow),
    accessible: String(filters.accessible),
  });
  if (filters.minAvailability) {
    params.set("min_availability", filters.minAvailability);
  }
  if (filters.amenities.length > 0) {
    params.set("amenities", filters.amenities.join(","));
  }
  return requestJson<RadarResponse>(`/api/v1/radar?${params.toString()}`);
}

export async function fetchStopArrivals(
  stopId: string,
  stopType = "U",
  limit = 6,
): Promise<ArrivalsResponse> {
  const params = new URLSearchParams({
    type: stopType,
    limit: String(limit),
  });
  return requestJson<ArrivalsResponse>(
    `/api/v1/stops/${encodeURIComponent(stopId)}/arrivals?${params.toString()}`,
  );
}

export async function fetchTripDetail(tripId: string): Promise<TripDetail> {
  return requestJson<TripDetail>(`/api/v1/trips/${encodeURIComponent(tripId)}`);
}

export async function fetchBikeSharing(): Promise<BikeSharingResponse> {
  return requestJson<BikeSharingResponse>("/api/v1/bikesharing");
}

export async function submitCheckin(
  spotId: string,
  level: 1 | 2 | 3,
  clientId = getOrCreateClientId(),
): Promise<CheckinResponse> {
  return requestJson<CheckinResponse>("/api/v1/checkins", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Client-ID": clientId,
    },
    body: JSON.stringify({ spot_id: spotId, level }),
  });
}

export function formatCountdownMinutes(
  isoTimestamp: string | null,
  nowMs = Date.now(),
): string {
  if (!isoTimestamp) return "—";
  const target = Date.parse(isoTimestamp);
  if (Number.isNaN(target)) return "—";
  const diffMin = Math.round((target - nowMs) / 60_000);
  if (diffMin <= 0) return "Due";
  return `${diffMin} min`;
}
