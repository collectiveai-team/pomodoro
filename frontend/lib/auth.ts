import { apiClient } from "./api-client";

/** The one error-response shape every backend endpoint returns (`ErrorResponse`, CES-4). */
interface ApiErrorBody {
  detail: string;
  code: string;
}

function isApiErrorBody(value: unknown): value is ApiErrorBody {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as Record<string, unknown>).detail === "string" &&
    typeof (value as Record<string, unknown>).code === "string"
  );
}

export class ApiError extends Error {
  readonly code: string;

  constructor(body: ApiErrorBody) {
    super(body.detail);
    this.code = body.code;
  }
}

function toApiError(error: unknown): ApiError {
  if (isApiErrorBody(error)) {
    return new ApiError(error);
  }
  return new ApiError({ detail: "Something went wrong. Please try again.", code: "unknown_error" });
}

export async function login(email: string, password: string): Promise<void> {
  const { error } = await apiClient.POST("/api/v1/auth/login", {
    body: { email, password },
  });
  if (error) {
    throw toApiError(error);
  }
}

export async function registerAccount(
  email: string,
  password: string,
  timeZone: string,
): Promise<void> {
  const { error } = await apiClient.POST("/api/v1/auth/register", {
    body: { email, password, time_zone: timeZone },
  });
  if (error) {
    throw toApiError(error);
  }
}
