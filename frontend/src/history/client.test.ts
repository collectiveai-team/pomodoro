import { afterEach, describe, expect, it, vi } from "vitest";
import {
  expectRequest,
  jsonResponse,
  stubSameOriginFetch,
} from "@/src/testing/fetch-stub";

async function importHistoryClientWithFetch(fetchMock: typeof fetch) {
  stubSameOriginFetch(fetchMock);
  return import("./client");
}

describe("history client wrappers", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it("requests the month heatmap with year/month as query params", async () => {
    const monthBody = [{ day: "2026-10-03", completed_count: 4 }];
    const fetchMock = vi.fn<typeof fetch>(async () => jsonResponse(monthBody));
    const { fetchMonthHeatmap } = await importHistoryClientWithFetch(fetchMock);

    const result = await fetchMonthHeatmap(2026, 10);

    const request = expectRequest(fetchMock, "GET", "/api/history/month");
    const url = new URL(request.url);
    expect(url.searchParams.get("year")).toBe("2026");
    expect(url.searchParams.get("month")).toBe("10");
    expect(result).toEqual({ ok: true, days: monthBody });
  });

  it("surfaces the server's message on a failed month fetch instead of a generic fallback", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () =>
      jsonResponse({ detail: "No autenticado." }, 401),
    );
    const { fetchMonthHeatmap } = await importHistoryClientWithFetch(fetchMock);

    const result = await fetchMonthHeatmap(2026, 10);

    expect(result).toEqual({
      ok: false,
      status: 401,
      message: "No autenticado.",
    });
  });

  it("requests the day detail with the date plus the same text/tags filter as the other tabs", async () => {
    const dayBody = [
      {
        task_id: 1,
        text: "Write the panel",
        tags: ["trabajo"],
        completed_count: 2,
        dedicated_seconds: 3000,
      },
    ];
    const fetchMock = vi.fn<typeof fetch>(async () => jsonResponse(dayBody));
    const { fetchDayDetail } = await importHistoryClientWithFetch(fetchMock);

    const result = await fetchDayDetail("2026-10-03", {
      text: "write",
      tags: ["trabajo", "sin etiqueta"],
    });

    const request = expectRequest(fetchMock, "GET", "/api/history/day");
    const url = new URL(request.url);
    expect(url.searchParams.get("date")).toBe("2026-10-03");
    expect(url.searchParams.get("text")).toBe("write");
    expect(url.searchParams.getAll("tags")).toEqual([
      "trabajo",
      "sin etiqueta",
    ]);
    expect(result).toEqual({ ok: true, summaries: dayBody });
  });

  it("surfaces the server's message on a failed day-detail fetch instead of a generic fallback", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () =>
      jsonResponse({ detail: "Fecha inválida." }, 422),
    );
    const { fetchDayDetail } = await importHistoryClientWithFetch(fetchMock);

    const result = await fetchDayDetail("2026-10-03", { text: "", tags: [] });

    expect(result).toEqual({
      ok: false,
      status: 422,
      message: "Fecha inválida.",
    });
  });
});
