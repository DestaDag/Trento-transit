import { describe, expect, it, vi } from "vitest";
import {
  formatCountdownMinutes,
  getOrCreateClientId,
  submitCheckin,
} from "../src/api/client";

describe("api client helpers", () => {
  it("persists and reuses X-Client-ID in storage", () => {
    const map = new Map<string, string>();
    const storage = {
      getItem: (k: string) => map.get(k) ?? null,
      setItem: (k: string, v: string) => {
        map.set(k, v);
      },
    };
    const first = getOrCreateClientId(storage);
    const second = getOrCreateClientId(storage);
    expect(first).toBeTruthy();
    expect(second).toBe(first);
  });

  it("formats countdown minutes cleanly", () => {
    const now = Date.parse("2026-11-26T10:00:00Z");
    expect(formatCountdownMinutes("2026-11-26T10:07:00Z", now)).toBe("7 min");
    expect(formatCountdownMinutes("2026-11-26T09:59:30Z", now)).toBe("Due");
    expect(formatCountdownMinutes(null, now)).toBe("—");
  });

  it("sends X-Client-ID header on check-in POST", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        spot_id: "buc",
        occupancy: { status: "Available", occupancy_percent: 0, source: "crowdsourced" },
        accepted: true,
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const res = await submitCheckin("buc", 1, "test-uuid-123");
    expect(res.accepted).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/checkins",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "X-Client-ID": "test-uuid-123",
        }),
      }),
    );
    vi.unstubAllGlobals();
  });
});
