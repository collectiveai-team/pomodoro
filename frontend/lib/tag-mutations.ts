import type { components } from "@/lib/api/schema";
import { apiClient } from "@/lib/api-client";
import { toApiError } from "@/lib/api-error";
import { redirectToLoginOn401 } from "@/lib/http-session";
import { refreshTagCatalog } from "@/lib/use-tag-catalog";

type UpdateTagBody = components["schemas"]["UpdateTagRequest"];

/** Outcome of a Tag mutation: `message` is the Spanish error to show, null on success. */
export interface TagMutationResult {
  message: string | null;
}

const SUCCESS: TagMutationResult = { message: null };

/** Renames and/or recolors one Tag, then refreshes the shared catalog. */
export async function updateTag(tagId: string, body: UpdateTagBody): Promise<TagMutationResult> {
  const { error, response } = await apiClient.PATCH("/api/v1/tags/{tag_id}", {
    params: { path: { tag_id: tagId } },
    body,
  });
  if (await redirectToLoginOn401(response)) {
    return SUCCESS;
  }
  if (error !== undefined) {
    return { message: toApiError(error).message };
  }
  refreshTagCatalog();
  return SUCCESS;
}

/** Deletes one Tag (it disappears from every Task), then refreshes the shared catalog. */
export async function deleteTag(tagId: string): Promise<TagMutationResult> {
  const { error, response } = await apiClient.DELETE("/api/v1/tags/{tag_id}", {
    params: { path: { tag_id: tagId } },
  });
  if (await redirectToLoginOn401(response)) {
    return SUCCESS;
  }
  if (error !== undefined) {
    return { message: toApiError(error).message };
  }
  refreshTagCatalog();
  return SUCCESS;
}

/** Replaces a Task's Tags by name (the API creates or reuses each Tag), refreshing the catalog. */
export async function setTaskTagNames(taskId: string, names: string[]): Promise<TagMutationResult> {
  const { error, response } = await apiClient.PATCH("/api/v1/tasks/{task_id}/tags", {
    params: { path: { task_id: taskId } },
    body: { names },
  });
  if (await redirectToLoginOn401(response)) {
    return SUCCESS;
  }
  if (error !== undefined) {
    return { message: toApiError(error).message };
  }
  refreshTagCatalog();
  return SUCCESS;
}
