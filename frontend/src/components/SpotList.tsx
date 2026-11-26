import { useState } from "react";
import { ApiError } from "../api/client";
import type {
  LinkedStop,
  OccupancyStatus,
  RadarSpotItem,
} from "../api/types";

interface SpotListProps {
  items: RadarSpotItem[];
  isLoading: boolean;
  selectedSpotId: string | null;
  onSelectSpot: (spotId: string) => void;
  onSelectStop: (stop: LinkedStop) => void;
  onCheckin: (spotId: string, level: 1 | 2 | 3) => Promise<unknown>;
}

const OCCUPANCY_BADGES: Record<
  OccupancyStatus,
  { icon: string; classes: string; label: string }
> = {
  Available: {
    icon: "●",
    classes: "bg-emerald-100 text-emerald-900 border-emerald-300",
    label: "Available",
  },
  Moderate: {
    icon: "◐",
    classes: "bg-amber-100 text-amber-900 border-amber-300",
    label: "Moderate",
  },
  Busy: {
    icon: "▲",
    classes: "bg-rose-100 text-rose-900 border-rose-300",
    label: "Busy",
  },
  Closed: {
    icon: "✕",
    classes: "bg-slate-200 text-slate-800 border-slate-300",
    label: "Closed",
  },
};

const SOURCE_LABELS = {
  live: "Live",
  crowdsourced: "Crowdsourced",
  estimated: "Estimated",
} as const;

export function SpotList({
  items,
  isLoading,
  selectedSpotId,
  onSelectSpot,
  onSelectStop,
  onCheckin,
}: SpotListProps) {
  const [checkinFeedback, setCheckinFeedback] = useState<
    Record<string, { type: "ok" | "error"; message: string }>
  >({});
  const [submittingSpot, setSubmittingSpot] = useState<string | null>(null);

  const handleCheckin = async (spotId: string, level: 1 | 2 | 3) => {
    setSubmittingSpot(spotId);
    try {
      await onCheckin(spotId, level);
      setCheckinFeedback((prev) => ({
        ...prev,
        [spotId]: { type: "ok", message: "Thanks! Occupancy updated." },
      }));
    } catch (err) {
      const message =
        err instanceof ApiError && err.status === 429
          ? "Rate limited: 1 check-in per 15 min."
          : err instanceof Error
            ? err.message
            : "Check-in failed";
      setCheckinFeedback((prev) => ({
        ...prev,
        [spotId]: { type: "error", message },
      }));
    } finally {
      setSubmittingSpot(null);
    }
  };

  if (isLoading && items.length === 0) {
    return (
      <div className="p-4 text-sm text-slate-600">
        Loading Trento study spots and transit radar...
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="p-4 text-sm text-slate-600">
        No study spots match the active filters.
      </div>
    );
  }

  return (
    <ul className="divide-y divide-slate-200" aria-label="Ranked study spots">
      {items.map(({ spot, distance_m, commute }) => {
        const badge = OCCUPANCY_BADGES[spot.occupancy.status];
        const isSelected = selectedSpotId === spot.spot_id;
        const feedback = checkinFeedback[spot.spot_id];

        return (
          <li
            key={spot.spot_id}
            className={`p-3.5 transition ${
              isSelected ? "bg-blue-50/70" : "bg-white hover:bg-slate-50"
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <button
                type="button"
                onClick={() => onSelectSpot(spot.spot_id)}
                className="text-left focus:outline-none"
              >
                <h2 className="text-sm font-bold text-slate-900">{spot.name}</h2>
                {spot.address && (
                  <p className="text-xs text-slate-600">{spot.address}</p>
                )}
              </button>

              <div className="flex flex-col items-end gap-1 shrink-0">
                <span
                  className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${badge.classes}`}
                >
                  <span aria-hidden="true">{badge.icon}</span>
                  <span>{badge.label}</span>
                  {spot.occupancy.occupancy_percent !== null && (
                    <span>({Math.round(spot.occupancy.occupancy_percent)}%)</span>
                  )}
                </span>
                <span className="text-[11px] font-medium text-slate-600">
                  {SOURCE_LABELS[spot.occupancy.source]}
                </span>
              </div>
            </div>

            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-700">
              <span className="rounded bg-slate-100 px-2 py-0.5 font-semibold text-slate-900">
                {commute.mode === "transit" ? "🚌 Transit" : "🚶 Walk"} ·{" "}
                {Math.round(commute.total_minutes)} min
              </span>
              <span className="text-slate-600">
                {(distance_m / 1000).toFixed(2)} km away
              </span>
              {spot.amenities.map((amenity) => (
                <span
                  key={amenity}
                  className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-700"
                >
                  {amenity.replace("_", " ")}
                </span>
              ))}
            </div>

            {spot.alerts.length > 0 && (
              <div className="mt-2 rounded border border-amber-300 bg-amber-50 px-2.5 py-1.5 text-xs text-amber-950">
                <strong>⚠ Service Alert:</strong>{" "}
                {spot.alerts[0].header || spot.alerts[0].details}
              </div>
            )}

            {spot.linked_stops.length > 0 && (
              <div className="mt-2 flex flex-wrap items-center gap-1.5">
                <span className="text-[11px] font-medium text-slate-600">
                  Stops:
                </span>
                {spot.linked_stops.slice(0, 3).map((stop) => (
                  <button
                    key={stop.stop_id}
                    type="button"
                    onClick={() => onSelectStop(stop)}
                    className="rounded-md border border-blue-200 bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-900 hover:bg-blue-100"
                  >
                    {stop.stop_name} ({Math.round(stop.walk_minutes)}m)
                  </button>
                ))}
              </div>
            )}

            {spot.occupancy.status !== "Closed" && (
              <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                <span className="text-[11px] font-medium text-slate-600">
                  Check in:
                </span>
                {(
                  [
                    [1, "Plenty of seats"],
                    [2, "Half full"],
                    [3, "Almost full"],
                  ] as const
                ).map(([level, label]) => (
                  <button
                    key={level}
                    type="button"
                    disabled={submittingSpot === spot.spot_id}
                    onClick={() => void handleCheckin(spot.spot_id, level)}
                    className="rounded border border-slate-300 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-800 hover:bg-slate-100 disabled:opacity-50"
                  >
                    {label}
                  </button>
                ))}
              </div>
            )}

            {feedback && (
              <p
                role="status"
                className={`mt-1.5 text-xs font-medium ${
                  feedback.type === "ok" ? "text-emerald-800" : "text-rose-800"
                }`}
              >
                {feedback.message}
              </p>
            )}
          </li>
        );
      })}
    </ul>
  );
}
