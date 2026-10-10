"use client";

import { useEffect, useState } from "react";
import type { components } from "@/lib/api/schema";
import { apiClient } from "@/lib/api-client";
import { redirectToLoginOn401 } from "@/lib/http-session";

type TagResponseBody = components["schemas"]["TagResponse"];

/** The caller's Tag catalog, shared by every filter UI (Tasks' two tabs, T22; History, T23). */
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
    return () => {
      cancelled = true;
    };
  }, []);

  return tags;
}
