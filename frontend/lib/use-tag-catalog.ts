"use client";

import { useEffect, useState } from "react";
import type { components } from "@/lib/api/schema";
import { apiClient } from "@/lib/api-client";
import { redirectToLoginOn401 } from "@/lib/http-session";

type TagResponseBody = components["schemas"]["TagResponse"];

/** Window event telling every mounted catalog consumer to reload (Tag created/renamed/deleted). */
export const TAG_CATALOG_CHANGED_EVENT = "pomodoro:tag-catalog-changed";

/** Refreshes every mounted `useTagCatalog` after a Tag mutation (Task Tag editor; Tag manager, T13). */
export function refreshTagCatalog(): void {
  window.dispatchEvent(new Event(TAG_CATALOG_CHANGED_EVENT));
}

/** The caller's Tag catalog, shared by every filter UI and Tag editor; reloads on `refreshTagCatalog`. */
export function useTagCatalog(): TagResponseBody[] {
  const [tags, setTags] = useState<TagResponseBody[]>([]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const { data, response } = await apiClient.GET("/api/v1/tags");
      if (cancelled) {
        return;
      }
      if (await redirectToLoginOn401(response)) {
        return;
      }
      setTags(data?.tags ?? []);
    }
    void load();
    const onChanged = () => void load();
    window.addEventListener(TAG_CATALOG_CHANGED_EVENT, onChanged);
    return () => {
      cancelled = true;
      window.removeEventListener(TAG_CATALOG_CHANGED_EVENT, onChanged);
    };
  }, []);

  return tags;
}
