import { describe, expect, it } from "vitest";
import { reorderedTaskIds } from "./task-reorder";

describe("reorderedTaskIds", () => {
  it("moves the dragged id to the drop target's position", () => {
    expect(reorderedTaskIds(["a", "b", "c"], "a", "c")).toEqual(["b", "c", "a"]);
  });

  it("moves an id earlier in the list", () => {
    expect(reorderedTaskIds(["a", "b", "c"], "c", "a")).toEqual(["c", "a", "b"]);
  });

  it("is a no-op when there is no drop target", () => {
    expect(reorderedTaskIds(["a", "b", "c"], "a", null)).toBeNull();
  });

  it("is a no-op when dropped back on itself", () => {
    expect(reorderedTaskIds(["a", "b", "c"], "b", "b")).toBeNull();
  });

  it("is a no-op when either id is unknown", () => {
    expect(reorderedTaskIds(["a", "b", "c"], "missing", "a")).toBeNull();
    expect(reorderedTaskIds(["a", "b", "c"], "a", "missing")).toBeNull();
  });
});
