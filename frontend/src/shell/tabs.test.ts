import { describe, expect, it } from "vitest";
import { isTabId, TAB_LABELS, TAB_ORDER } from "./tabs";

describe("tabs", () => {
  it("has a label for every tab in TAB_ORDER", () => {
    for (const tab of TAB_ORDER) {
      expect(TAB_LABELS[tab]).toBeTypeOf("string");
      expect(TAB_LABELS[tab].length).toBeGreaterThan(0);
    }
  });

  it("isTabId accepts only known tab ids", () => {
    for (const tab of TAB_ORDER) {
      expect(isTabId(tab)).toBe(true);
    }
    expect(isTabId("settings")).toBe(false);
    expect(isTabId("")).toBe(false);
  });
});
