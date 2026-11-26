import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import {
  fetchBikeSharing,
  fetchRadar,
  fetchStopArrivals,
  submitCheckin,
} from "../api/client";
import type { LinkedStop, RadarFilters } from "../api/types";

export const DEFAULT_ORIGIN = { lat: 46.0679, lon: 11.1211 };

export const INITIAL_FILTERS: RadarFilters = {
  openNow: false,
  minAvailability: "",
  accessible: false,
  amenities: [],
  showBikeSharing: false,
};

export function useRadarData() {
  const queryClient = useQueryClient();
  const [origin, setOrigin] = useState<{ lat: number; lon: number }>(DEFAULT_ORIGIN);
  const [geoStatus, setGeoStatus] = useState<"pending" | "granted" | "fallback">("pending");
  const [filters, setFilters] = useState<RadarFilters>(INITIAL_FILTERS);
  const [selectedStop, setSelectedStop] = useState<LinkedStop | null>(null);

  const requestGeolocation = useCallback(() => {
    if (typeof navigator === "undefined" || !("geolocation" in navigator)) {
      setGeoStatus("fallback");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setOrigin({ lat: pos.coords.latitude, lon: pos.coords.longitude });
        setGeoStatus("granted");
      },
      () => {
        setGeoStatus("fallback");
      },
      { enableHighAccuracy: false, timeout: 6000, maximumAge: 60_000 },
    );
  }, []);

  useEffect(() => {
    requestGeolocation();
  }, [requestGeolocation]);

  const radarQuery = useQuery({
    queryKey: ["radar", origin.lat, origin.lon, filters],
    queryFn: () => fetchRadar(origin.lat, origin.lon, filters),
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
    staleTime: 20_000,
  });

  const bikeQuery = useQuery({
    queryKey: ["bikesharing"],
    queryFn: fetchBikeSharing,
    enabled: filters.showBikeSharing,
    refetchInterval: 60_000,
    refetchIntervalInBackground: false,
    staleTime: 45_000,
  });

  const arrivalsQuery = useQuery({
    queryKey: ["stop-arrivals", selectedStop?.stop_id, selectedStop?.stop_type],
    queryFn: () =>
      fetchStopArrivals(selectedStop!.stop_id, selectedStop!.stop_type, 6),
    enabled: selectedStop !== null,
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
    staleTime: 20_000,
  });

  const checkinMutation = useMutation({
    mutationFn: ({ spotId, level }: { spotId: string; level: 1 | 2 | 3 }) =>
      submitCheckin(spotId, level),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["radar"] });
    },
  });

  return {
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
  };
}
