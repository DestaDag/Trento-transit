import type { RadarFilters } from "../api/types";

interface FilterBarProps {
  filters: RadarFilters;
  onChange: (next: RadarFilters) => void;
}

const AMENITY_OPTIONS = [
  { id: "wifi", label: "Wi-Fi" },
  { id: "outlets", label: "Outlets" },
  { id: "quiet_zone", label: "Quiet Zone" },
];

export function FilterBar({ filters, onChange }: FilterBarProps) {
  const toggleAmenity = (amenity: string) => {
    const exists = filters.amenities.includes(amenity);
    const nextAmenities = exists
      ? filters.amenities.filter((a) => a !== amenity)
      : [...filters.amenities, amenity];
    onChange({ ...filters, amenities: nextAmenities });
  };

  return (
    <div
      className="flex flex-wrap items-center gap-2 border-b border-slate-200 bg-white px-3 py-2.5"
      aria-label="Study spot filters"
    >
      <button
        type="button"
        onClick={() => onChange({ ...filters, openNow: !filters.openNow })}
        aria-pressed={filters.openNow}
        className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${
          filters.openNow
            ? "bg-blue-700 text-white"
            : "bg-slate-100 text-slate-800 hover:bg-slate-200"
        }`}
      >
        Open Now
      </button>

      <button
        type="button"
        onClick={() => onChange({ ...filters, accessible: !filters.accessible })}
        aria-pressed={filters.accessible}
        className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${
          filters.accessible
            ? "bg-blue-700 text-white"
            : "bg-slate-100 text-slate-800 hover:bg-slate-200"
        }`}
      >
        Wheelchair Accessible
      </button>

      <select
        aria-label="Minimum availability"
        value={filters.minAvailability}
        onChange={(e) =>
          onChange({
            ...filters,
            minAvailability: e.target.value as RadarFilters["minAvailability"],
          })
        }
        className="rounded-full border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-800"
      >
        <option value="">Any Seats</option>
        <option value="Available">Available (&lt;50%)</option>
        <option value="Moderate">Moderate (&le;80%)</option>
      </select>

      {AMENITY_OPTIONS.map((item) => {
        const active = filters.amenities.includes(item.id);
        return (
          <button
            key={item.id}
            type="button"
            onClick={() => toggleAmenity(item.id)}
            aria-pressed={active}
            className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${
              active
                ? "bg-emerald-700 text-white"
                : "bg-slate-100 text-slate-800 hover:bg-slate-200"
            }`}
          >
            {item.label}
          </button>
        );
      })}

      <button
        type="button"
        onClick={() =>
          onChange({ ...filters, showBikeSharing: !filters.showBikeSharing })
        }
        aria-pressed={filters.showBikeSharing}
        className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${
          filters.showBikeSharing
            ? "bg-amber-700 text-white"
            : "bg-slate-100 text-slate-800 hover:bg-slate-200"
        }`}
      >
        Bike-Sharing
      </button>
    </div>
  );
}
