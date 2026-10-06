"use client";

import { useCallback, useEffect, useState } from "react";
import {
  fetchTagCatalog,
  fetchTaskCounts,
  type TagPublic,
  type TaskCounts,
  type TaskFilterQuery,
  type TaskListResult,
  type TaskPublic,
} from "./client";

/**
 * Shared by `ActiveTab` and `ArchivedTab`: debounced text+tag-chip filtering
 * against a tab-specific list endpoint, the Tag catalog the filter's chips
 * are built from, and the tab's count from `/api/tasks/summary`.
 */
export function useFilteredTaskList(
  fetchTasks: (filter: TaskFilterQuery) => Promise<TaskListResult>,
  countField: keyof TaskCounts,
) {
  const [tasks, setTasks] = useState<TaskPublic[]>([]);
  const [count, setCount] = useState<number | null>(null);
  const [tagCatalog, setTagCatalog] = useState<TagPublic[]>([]);
  const [availableTags, setAvailableTags] = useState<string[]>([]);
  const [textFilter, setTextFilter] = useState("");
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [listError, setListError] = useState<string | null>(null);

  const loadTasks = useCallback(async (): Promise<void> => {
    const result = await fetchTasks({
      text: textFilter.trim(),
      tags: selectedTags,
    });
    if (result.ok) {
      setTasks(result.tasks);
      setListError(null);
    } else {
      setListError(result.message);
    }
  }, [fetchTasks, textFilter, selectedTags]);

  const loadCounts = useCallback(async (): Promise<void> => {
    const counts = await fetchTaskCounts();
    if (counts) {
      setCount(counts[countField]);
    }
  }, [countField]);

  const refreshTagCatalog = useCallback(async (): Promise<void> => {
    const catalog = await fetchTagCatalog();
    setTagCatalog(catalog);
    setAvailableTags(catalog.map((tag) => tag.name));
  }, []);

  useEffect(() => {
    void refreshTagCatalog();
    void loadCounts();
  }, [refreshTagCatalog, loadCounts]);

  useEffect(() => {
    const handle = setTimeout(() => {
      void loadTasks();
    }, 250);
    return () => clearTimeout(handle);
  }, [loadTasks]);

  function toggleTag(tag: string): void {
    setSelectedTags((previous) =>
      previous.includes(tag)
        ? previous.filter((existing) => existing !== tag)
        : [...previous, tag],
    );
  }

  return {
    tasks,
    setTasks,
    count,
    tagCatalog,
    availableTags,
    textFilter,
    setTextFilter,
    selectedTags,
    toggleTag,
    listError,
    setListError,
    loadCounts,
    refreshTagCatalog,
  };
}
