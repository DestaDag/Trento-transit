import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { FilterBar } from "./components/FilterBar";
import { RadarMap } from "./components/RadarMap";
import { SpotList } from "./components/SpotList";
import { StopArrivalsDrawer } from "./components/StopArrivalsDrawer";
import { useRadarData } from "./hooks/useRadarData";

const queryClient = new QueryClient();

function RadarDashboard() {
  const {
    origin,
    setOrigin,
    geoStatus,
    requestGeolocation,
    filters,
    setFilters,
    selectedStop,
    setSelectedStop,
    radarQuery,
    bikeQuery,
    arrivalsQuery,
    checkinMutation,
  } = useRadarData();

  const [selectedSpotId, setSelectedSpotId] = useState<string | null>(null);
  const [sheetExpanded, setSheetExpanded] = useState(true);

  const radarData = radarQuery.data;
  const lastUpdated = radarData?.updated_at
    ? new Date(radarData.updated_at).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    : null;

  return (
    <div className="flex h-dvh w-full flex-col overflow-hidden bg-slate-50">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-slate-900 px-3 py-2 text-white">
        <div className="min-w-0">
          <h1 className="truncate text-sm font-bold sm:text-base">
            Trento Transit &amp; Study Spot Radar
          </h1>
          <p className="text-[11px] text-slate-300">
            {lastUpdated ? `Last updated ${lastUpdated}` : "Connecting..."}
            {radarData?.stale && " · Cached / Stale transit"}
            {geoStatus === "fallback" && " · Origin: Piazza Duomo"}
          </p>
        </div>

        <button
          type="button"
          onClick={requestGeolocation}
          className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-500"
        >
          📍 Locate me
        </button>
      </header>

      <FilterBar filters={filters} onChange={setFilters} />

      <main className="relative flex flex-1 flex-col overflow-hidden lg:flex-row">
        <section
          aria-label="Study spot list"
          className={`z-10 flex flex-col border-t border-slate-200 bg-white lg:order-1 lg:w-[420px] lg:shrink-0 lg:border-t-0 lg:border-r ${
            sheetExpanded
              ? "order-2 h-[48%] lg:h-full"
              : "order-2 h-12 lg:h-full"
          }`}
        >
          <button
            type="button"
            onClick={() => setSheetExpanded((v) => !v)}
            className="flex items-center justify-between border-b border-slate-200 bg-slate-100 px-3 py-2 text-xs font-semibold text-slate-800 lg:hidden"
          >
            <span>
              Study Spots ({radarData?.spots.length ?? 0})
            </span>
            <span>{sheetExpanded ? "▼ Collapse" : "▲ Expand"}</span>
          </button>

          <div className="flex-1 overflow-y-auto">
            <SpotList
              items={radarData?.spots ?? []}
              isLoading={radarQuery.isLoading}
              selectedSpotId={selectedSpotId}
              onSelectSpot={(id) => setSelectedSpotId(id)}
              onSelectStop={(stop) => setSelectedStop(stop)}
              onCheckin={(spotId, level) =>
                checkinMutation.mutateAsync({ spotId, level })
              }
            />
          </div>
        </section>

        <section
          aria-label="Interactive Trento map"
          className="order-1 flex-1 lg:order-2"
        >
          <RadarMap
            origin={origin}
            onOriginChange={setOrigin}
            spots={radarData?.spots ?? []}
            stops={radarData?.nearby_stops ?? []}
            bikeStations={bikeQuery.data?.stations ?? []}
            showBikeSharing={filters.showBikeSharing}
            selectedSpotId={selectedSpotId}
            onSelectSpot={(id) => setSelectedSpotId(id)}
            onSelectStop={(stop) => setSelectedStop(stop)}
          />
        </section>
      </main>

      <StopArrivalsDrawer
        stop={selectedStop}
        arrivals={arrivalsQuery.data}
        isLoading={arrivalsQuery.isLoading}
        isError={arrivalsQuery.isError}
        onClose={() => setSelectedStop(null)}
      />
    </div>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RadarDashboard />
    </QueryClientProvider>
  );
}

export default App;
