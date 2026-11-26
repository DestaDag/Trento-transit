import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../src/api/client";
import type { RadarSpotItem } from "../src/api/types";
import { FilterBar } from "../src/components/FilterBar";
import { SpotList } from "../src/components/SpotList";
import { INITIAL_FILTERS } from "../src/hooks/useRadarData";

const SAMPLE_ITEMS: RadarSpotItem[] = [
  {
    spot: {
      spot_id: "buc",
      name: "Biblioteca Universitaria Centrale",
      address: "Via Calepina 1",
      lat: 46.0697,
      lon: 11.1211,
      hours: {},
      capacity_tier: "large",
      amenities: ["wifi", "outlets", "quiet_zone", "accessible"],
      occupancy: {
        status: "Available",
        occupancy_percent: 32,
        source: "estimated",
      },
      linked_stops: [
        {
          stop_id: "2001",
          stop_code: "2001",
          stop_name: "Piazza Duomo",
          stop_type: "U",
          lat: 46.0679,
          lon: 11.1211,
          wheelchair_boarding: 1,
          walk_distance_m: 180,
          walk_minutes: 2.2,
          routes: [],
        },
      ],
      alerts: [],
    },
    distance_m: 200,
    commute: {
      mode: "walk",
      total_minutes: 2.5,
      walk_to_stop_minutes: 0,
      wait_minutes: 0,
      transit_minutes: 0,
      walk_from_stop_minutes: 0,
      origin_stop: null,
      destination_stop: null,
      next_departure: null,
    },
    score: 2.5,
  },
];

describe("FilterBar and SpotList", () => {
  it("toggles filter pills", () => {
    const onChange = vi.fn();
    render(<FilterBar filters={INITIAL_FILTERS} onChange={onChange} />);

    fireEvent.click(screen.getByRole("button", { name: "Open Now" }));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ openNow: true }),
    );
  });

  it("renders occupancy badge and handles 429 check-in rate limit", async () => {
    const onCheckin = vi
      .fn()
      .mockRejectedValueOnce(new ApiError(429, "Rate limit exceeded"));

    render(
      <SpotList
        items={SAMPLE_ITEMS}
        isLoading={false}
        selectedSpotId={null}
        onSelectSpot={() => {}}
        onSelectStop={() => {}}
        onCheckin={onCheckin}
      />,
    );

    expect(screen.getByText("Available")).toBeInTheDocument();
    expect(screen.getByText("Estimated")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Plenty of seats" }));
    await waitFor(() => {
      expect(
        screen.getByText("Rate limited: 1 check-in per 15 min."),
      ).toBeInTheDocument();
    });
  });
});
