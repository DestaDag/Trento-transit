import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { fetchTripDetail, formatCountdownMinutes } from "../api/client";
import type { ArrivalsResponse, LinkedStop } from "../api/types";

interface StopArrivalsDrawerProps {
  stop: LinkedStop | null;
  arrivals: ArrivalsResponse | undefined;
  isLoading: boolean;
  isError: boolean;
  onClose: () => void;
}

export function StopArrivalsDrawer({
  stop,
  arrivals,
  isLoading,
  isError,
  onClose,
}: StopArrivalsDrawerProps) {
  const [expandedTripId, setExpandedTripId] = useState<string | null>(null);

  const tripDetailQuery = useQuery({
    queryKey: ["trip-detail", expandedTripId],
    queryFn: () => fetchTripDetail(expandedTripId!),
    enabled: expandedTripId !== null,
    staleTime: 30_000,
  });

  if (!stop) return null;

  return (
    <aside
      aria-label={`Departures for ${stop.stop_name}`}
      className="fixed inset-x-0 bottom-0 z-[1000] max-h-[65vh] overflow-y-auto rounded-t-2xl border-t border-slate-300 bg-white p-4 shadow-2xl lg:inset-x-auto lg:right-4 lg:bottom-4 lg:w-96 lg:rounded-xl lg:border"
    >
      <div className="flex items-start justify-between gap-2 border-b border-slate-200 pb-2.5">
        <div>
          <h3 className="text-base font-bold text-slate-900">{stop.stop_name}</h3>
          <p className="text-xs text-slate-600">
            Stop {stop.stop_code || stop.stop_id} ·{" "}
            {stop.wheelchair_boarding > 0 ? "♿ Accessible" : "Standard stop"}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close departures drawer"
          className="rounded-lg px-2 py-1 text-sm font-semibold text-slate-700 hover:bg-slate-100"
        >
          ✕
        </button>
      </div>

      {arrivals?.stale && (
        <div className="mt-2 rounded border border-amber-300 bg-amber-50 px-2.5 py-1.5 text-xs font-medium text-amber-950">
          Cached / Stale transit data — upstream feed temporarily unavailable.
        </div>
      )}

      {arrivals && arrivals.alerts.length > 0 && (
        <div className="mt-2 space-y-1">
          {arrivals.alerts.map((alert, idx) => (
            <div
              key={`${alert.route_id}-${idx}`}
              className="rounded border border-amber-300 bg-amber-50 px-2.5 py-1.5 text-xs text-amber-950"
            >
              <div className="font-semibold">
                ⚠ {alert.route_short_name ? `Line ${alert.route_short_name}: ` : ""}
                {alert.header}
              </div>
              {alert.details && <p className="mt-0.5">{alert.details}</p>}
              {alert.url && (
                <a
                  href={alert.url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-0.5 inline-block underline"
                >
                  More info
                </a>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="mt-3">
        {isLoading && <p className="text-xs text-slate-600">Loading departures...</p>}
        {isError && (
          <p className="text-xs text-rose-800">
            Could not load departures for this stop.
          </p>
        )}
        {!isLoading && !isError && arrivals?.departures.length === 0 && (
          <p className="text-xs text-slate-600">No upcoming departures found.</p>
        )}

        <ul className="space-y-2">
          {arrivals?.departures.map((dep) => {
            const targetIso = dep.effective_arrival || dep.scheduled_arrival;
            const countdown = formatCountdownMinutes(targetIso);
            const isExpanded = expandedTripId === dep.trip_id;

            return (
              <li
                key={dep.trip_id}
                className="rounded-lg border border-slate-200 bg-slate-50 p-2.5"
              >
                <button
                  type="button"
                  onClick={() =>
                    setExpandedTripId(isExpanded ? null : dep.trip_id)
                  }
                  className="flex w-full items-center justify-between gap-2 text-left"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span
                        className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                        style={{ backgroundColor: dep.route_color || "#1976D2" }}
                      />
                      <span className="truncate text-sm font-semibold text-slate-900">
                        {dep.trip_headsign || `Route ${dep.route_id ?? ""}`}
                      </span>
                    </div>
                    <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[11px] text-slate-700">
                      <span>
                        {dep.is_realtime ? "● Real-time" : "○ Scheduled"}
                      </span>
                      {dep.delay_minutes !== null && dep.delay_minutes > 0 && (
                        <span className="rounded bg-rose-100 px-1.5 py-0.5 font-semibold text-rose-900">
                          +{dep.delay_minutes} min
                        </span>
                      )}
                      {dep.delay_minutes === 0 && (
                        <span className="rounded bg-emerald-100 px-1.5 py-0.5 font-semibold text-emerald-900">
                          On time
                        </span>
                      )}
                      {dep.wheelchair_accessible === 1 && <span>♿</span>}
                    </div>
                  </div>
                  <span className="shrink-0 text-sm font-bold text-blue-900">
                    {countdown}
                  </span>
                </button>

                {isExpanded && (
                  <div className="mt-2 border-t border-slate-200 pt-2 text-xs text-slate-700">
                    {tripDetailQuery.isLoading && <p>Loading stops...</p>}
                    {tripDetailQuery.data && (
                      <ol className="max-h-36 space-y-1 overflow-y-auto pl-3">
                        {tripDetailQuery.data.stop_times.map((st) => (
                          <li key={`${st.stop_id}-${st.stop_sequence}`}>
                            <span className="font-medium">
                              {st.stop_name || st.stop_id}
                            </span>{" "}
                            <span className="text-slate-500">
                              {st.departure_time || st.arrival_time || ""}
                            </span>
                          </li>
                        ))}
                      </ol>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </div>
    </aside>
  );
}
