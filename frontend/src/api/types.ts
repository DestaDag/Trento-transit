export type OccupancyStatus = "Available" | "Moderate" | "Busy" | "Closed";
export type OccupancySource = "live" | "crowdsourced" | "estimated";

export interface RouteNews {
  header: string | null;
  details: string | null;
  url: string | null;
  start_date: string | null;
  end_date: string | null;
  route_id: string | null;
  route_short_name: string | null;
}

export interface LinkedStop {
  stop_id: string;
  stop_code: string | null;
  stop_name: string;
  stop_type: "U" | "E" | string;
  lat: number;
  lon: number;
  wheelchair_boarding: number;
  walk_distance_m: number;
  walk_minutes: number;
  routes: Array<Record<string, unknown>>;
}

export interface OccupancyInfo {
  status: OccupancyStatus;
  occupancy_percent: number | null;
  source: OccupancySource;
}

export interface StudySpot {
  spot_id: string;
  name: string;
  address: string | null;
  lat: number;
  lon: number;
  hours: Record<string, Array<{ open: string; close: string }>>;
  capacity_tier: string;
  amenities: string[];
  occupancy: OccupancyInfo;
  linked_stops: LinkedStop[];
  alerts: RouteNews[];
}

export interface StopTimeItem {
  stop_id: string;
  stop_code: string | null;
  stop_name: string | null;
  stop_sequence: number;
  arrival_time: string | null;
  departure_time: string | null;
}

export interface Departure {
  trip_id: string;
  route_id: string | null;
  trip_headsign: string | null;
  scheduled_arrival: string | null;
  effective_arrival: string | null;
  delay_minutes: number | null;
  is_realtime: boolean;
  wheelchair_accessible: number | null;
  route_color: string | null;
  matricola_bus: string | null;
  stale: boolean;
}

export interface TripDetail extends Departure {
  stop_times: StopTimeItem[];
}

export interface ArrivalsResponse {
  stop_id: string;
  stop_type: string;
  departures: Departure[];
  alerts: RouteNews[];
  stale: boolean;
  updated_at: string;
}

export interface CommuteEstimate {
  mode: "walk" | "transit";
  total_minutes: number;
  walk_to_stop_minutes: number;
  wait_minutes: number;
  transit_minutes: number;
  walk_from_stop_minutes: number;
  origin_stop: LinkedStop | null;
  destination_stop: LinkedStop | null;
  next_departure: Departure | null;
}

export interface RadarSpotItem {
  spot: StudySpot;
  distance_m: number;
  commute: CommuteEstimate;
  score: number;
}

export interface RadarResponse {
  origin: { lat: number; lon: number };
  spots: RadarSpotItem[];
  nearby_stops: LinkedStop[];
  stale: boolean;
  updated_at: string;
}

export interface BikeStation {
  id: string;
  name: string;
  address: string | null;
  lat: number;
  lon: number;
  bikes: number;
  slots: number;
  total_slots: number;
}

export interface BikeSharingResponse {
  stations: BikeStation[];
  stale: boolean;
  updated_at: string;
}

export interface CheckinResponse {
  spot_id: string;
  occupancy: OccupancyInfo;
  accepted: boolean;
}

export interface RadarFilters {
  openNow: boolean;
  minAvailability: "" | "Available" | "Moderate" | "Busy";
  accessible: boolean;
  amenities: string[];
  showBikeSharing: boolean;
}
