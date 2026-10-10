import { describe, expect, it } from "vitest";
import { monthTitle, nextMonth, previousMonth } from "./history-navigation";

describe("nextMonth", () => {
  it("advances within the same year", () => {
    expect(nextMonth({ year: 2026, month: 3 })).toEqual({ year: 2026, month: 4 });
  });

  it("rolls over from December into January of the following year", () => {
    expect(nextMonth({ year: 2026, month: 12 })).toEqual({ year: 2027, month: 1 });
  });
});

describe("previousMonth", () => {
  it("goes back within the same year", () => {
    expect(previousMonth({ year: 2026, month: 3 })).toEqual({ year: 2026, month: 2 });
  });

  it("rolls back from January into December of the previous year", () => {
    expect(previousMonth({ year: 2026, month: 1 })).toEqual({ year: 2025, month: 12 });
  });
});

describe("nextMonth / previousMonth are inverses", () => {
  it("returns to the starting month across a year boundary", () => {
    const start = { year: 2026, month: 12 };
    expect(previousMonth(nextMonth(start))).toEqual(start);
  });
});

describe("monthTitle", () => {
  it("renders a capitalized Spanish month name with the year", () => {
    expect(monthTitle({ year: 2026, month: 10 })).toBe("Octubre 2026");
  });

  it("renders January correctly at a year boundary", () => {
    expect(monthTitle({ year: 2027, month: 1 })).toBe("Enero 2027");
  });
});
