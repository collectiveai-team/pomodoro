import { describe, expect, it } from "vitest";
import {
  buildTaskListQuery,
  EMPTY_TASK_FILTER,
  toggleTagFilter,
  UNTAGGED_FILTER,
} from "./task-filter";

describe("buildTaskListQuery", () => {
  it("sends no params with no text and no Tags selected (Story 44)", () => {
    expect(buildTaskListQuery(EMPTY_TASK_FILTER)).toEqual({});
  });

  it("sends only q for a text-only filter", () => {
    expect(buildTaskListQuery({ query: "repo", selectedTags: [] })).toEqual({ q: "repo" });
  });

  it("trims the text query and drops it entirely when it is blank", () => {
    expect(buildTaskListQuery({ query: "   ", selectedTags: [] })).toEqual({});
    expect(buildTaskListQuery({ query: "  repo  ", selectedTags: [] })).toEqual({ q: "repo" });
  });

  it("sends every selected Tag id as one array — the server ORs them (Story 41)", () => {
    expect(buildTaskListQuery({ query: "", selectedTags: ["tag-a", "tag-b"] })).toEqual({
      tags: ["tag-a", "tag-b"],
    });
  });

  it("sends the untagged sentinel alongside Tag ids (Story 42)", () => {
    expect(buildTaskListQuery({ query: "", selectedTags: [UNTAGGED_FILTER, "tag-a"] })).toEqual({
      tags: ["sin etiqueta", "tag-a"],
    });
  });

  it("sends both q and tags together — the server ANDs text with the Tag OR-group (Story 43)", () => {
    expect(buildTaskListQuery({ query: "repo", selectedTags: ["tag-a"] })).toEqual({
      q: "repo",
      tags: ["tag-a"],
    });
  });
});

describe("toggleTagFilter", () => {
  it("adds an unselected Tag", () => {
    const next = toggleTagFilter(EMPTY_TASK_FILTER, "tag-a");
    expect(next.selectedTags).toEqual(["tag-a"]);
  });

  it("removes an already-selected Tag", () => {
    const state = { query: "", selectedTags: ["tag-a", "tag-b"] };
    expect(toggleTagFilter(state, "tag-a").selectedTags).toEqual(["tag-b"]);
  });

  it("leaves the text query untouched", () => {
    const state = { query: "repo", selectedTags: [] };
    expect(toggleTagFilter(state, UNTAGGED_FILTER).query).toBe("repo");
  });
});
