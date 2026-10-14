import { describe, expect, it } from "vitest";
import { dayLabel, groupByMonth, rangeLabel } from "./task-history-format";

const days = [
  { day: "2026-10-14", completed_count: 2, dedicated_seconds: 3000 },
  { day: "2026-10-02", completed_count: 1, dedicated_seconds: 1500 },
  { day: "2026-09-30", completed_count: 3, dedicated_seconds: 5400 },
];

describe("groupByMonth", () => {
  it("groups days into months newest first with each month's totals", () => {
    const months = groupByMonth(days);
    expect(months.map((month) => month.key)).toEqual(["2026-10", "2026-09"]);
    expect(months[0]).toMatchObject({ completedCount: 3, dedicatedSeconds: 4500 });
    expect(months[0]?.days.map((entry) => entry.day)).toEqual(["2026-10-14", "2026-10-02"]);
    expect(months[1]).toMatchObject({ completedCount: 3, dedicatedSeconds: 5400 });
  });

  it("returns no months for no days", () => {
    expect(groupByMonth([])).toEqual([]);
  });
});

describe("dayLabel", () => {
  it("says Hoy for today and d/m/aaaa otherwise", () => {
    expect(dayLabel("2026-10-14", "2026-10-14")).toBe("Hoy");
    expect(dayLabel("2026-10-02", "2026-10-14")).toBe("2/10/2026");
  });
});

describe("rangeLabel", () => {
  it("formats the range with the distinct day count", () => {
    expect(rangeLabel("2026-09-02", "2026-10-13", 18)).toBe("2/9/2026 – 13/10/2026 · 18 días");
    expect(rangeLabel("2026-10-13", "2026-10-13", 1)).toBe("13/10/2026 – 13/10/2026 · 1 día");
  });
});
