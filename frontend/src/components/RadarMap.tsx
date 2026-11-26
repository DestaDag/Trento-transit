import L from "leaflet";
import "leaflet.markercluster";
import { useEffect, useMemo, useRef } from "react";
import {
  CircleMarker,
  MapContainer,
  Marker,
  Popup,
  TileLayer,
  useMap,
  useMapEvents,
} from "react-leaflet";
import type {
  BikeStation,
  LinkedStop,
  OccupancyStatus,
  RadarSpotItem,
} from "../api/types";

interface RadarMapProps {
  origin: { lat: number; lon: number };
  onOriginChange: (next: { lat: number; lon: number }) => void;
  spots: RadarSpotItem[];
  stops: LinkedStop[];
  bikeStations: BikeStation[];
  showBikeSharing: boolean;
  selectedSpotId: string | null;
  onSelectSpot: (spotId: string) => void;
  onSelectStop: (stop: LinkedStop) => void;
}

const TILE_URL =
  import.meta.env.VITE_OSM_TILE_URL ||
  "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";

const STATUS_COLORS: Record<OccupancyStatus, string> = {
  Available: "#059669",
  Moderate: "#d97706",
  Busy: "#dc2626",
  Closed: "#64748b",
};

const originIcon = L.divIcon({
  className: "origin-pin",
  html: '<div style="width:18px;height:18px;border-radius:9999px;background:#1d4ed8;border:3px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.4)"></div>',
  iconSize: [18, 18],
  iconAnchor: [9, 9],
});

function OriginClickHandler({
  onOriginChange,
}: {
  onOriginChange: (next: { lat: number; lon: number }) => void;
}) {
  useMapEvents({
    click(e) {
      onOriginChange({ lat: e.latlng.lat, lon: e.latlng.lng });
    },
  });
  return null;
}

function ClusteredStopsLayer({
  stops,
  onSelectStop,
}: {
  stops: LinkedStop[];
  onSelectStop: (stop: LinkedStop) => void;
}) {
  const map = useMap();
  const groupRef = useRef<L.MarkerClusterGroup | null>(null);

  useEffect(() => {
    const clusterGroup = L.markerClusterGroup({
      maxClusterRadius: 40,
      disableClusteringAtZoom: 16,
    });
    for (const stop of stops) {
      const marker = L.circleMarker([stop.lat, stop.lon], {
        radius: 6,
        color: "#0f172a",
        weight: 1.5,
        fillColor: "#38bdf8",
        fillOpacity: 0.9,
      });
      marker.bindTooltip(stop.stop_name, { direction: "top" });
      marker.on("click", () => onSelectStop(stop));
      clusterGroup.addLayer(marker);
    }
    map.addLayer(clusterGroup);
    groupRef.current = clusterGroup;
    return () => {
      map.removeLayer(clusterGroup);
    };
  }, [map, stops, onSelectStop]);

  return null;
}

export function RadarMap({
  origin,
  onOriginChange,
  spots,
  stops,
  bikeStations,
  showBikeSharing,
  selectedSpotId,
  onSelectSpot,
  onSelectStop,
}: RadarMapProps) {
  const uniqueStops = useMemo(() => {
    const seen = new Map<string, LinkedStop>();
    for (const s of stops) seen.set(s.stop_id, s);
    for (const item of spots) {
      for (const s of item.spot.linked_stops) {
        if (!seen.has(s.stop_id)) seen.set(s.stop_id, s);
      }
    }
    return Array.from(seen.values());
  }, [stops, spots]);

  return (
    <MapContainer
      center={[origin.lat, origin.lon]}
      zoom={14}
      className="h-full w-full"
      scrollWheelZoom
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url={TILE_URL}
      />
      <OriginClickHandler onOriginChange={onOriginChange} />

      <Marker
        position={[origin.lat, origin.lon]}
        icon={originIcon}
        draggable
        eventHandlers={{
          dragend(e) {
            const pos = e.target.getLatLng();
            onOriginChange({ lat: pos.lat, lon: pos.lng });
          },
        }}
      >
        <Popup>Your Origin (drag or click map to move)</Popup>
      </Marker>

      <ClusteredStopsLayer stops={uniqueStops} onSelectStop={onSelectStop} />

      {spots.map(({ spot, commute }) => {
        const color = STATUS_COLORS[spot.occupancy.status];
        const isSelected = selectedSpotId === spot.spot_id;
        return (
          <CircleMarker
            key={spot.spot_id}
            center={[spot.lat, spot.lon]}
            radius={isSelected ? 12 : 9}
            pathOptions={{
              color: isSelected ? "#0f172a" : "#ffffff",
              weight: isSelected ? 3 : 2,
              fillColor: color,
              fillOpacity: 0.95,
            }}
            eventHandlers={{
              click: () => onSelectSpot(spot.spot_id),
            }}
          >
            <Popup>
              <div className="text-xs">
                <p className="font-bold">{spot.name}</p>
                <p>
                  {spot.occupancy.status} · {Math.round(commute.total_minutes)} min
                </p>
              </div>
            </Popup>
          </CircleMarker>
        );
      })}

      {showBikeSharing &&
        bikeStations.map((station) => (
          <CircleMarker
            key={station.id}
            center={[station.lat, station.lon]}
            radius={7}
            pathOptions={{
              color: "#78350f",
              weight: 1.5,
              fillColor: "#f59e0b",
              fillOpacity: 0.9,
            }}
          >
            <Popup>
              <div className="text-xs">
                <p className="font-bold">{station.name}</p>
                <p>
                  🚲 {station.bikes} bikes · {station.slots} free slots
                </p>
              </div>
            </Popup>
          </CircleMarker>
        ))}
    </MapContainer>
  );
}
