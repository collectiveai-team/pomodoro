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

/** Parses any openapi-fetch `error` value into the shared `ErrorResponse` shape. */
export function toApiError(error: unknown): ApiError {
  if (isApiErrorBody(error)) {
    return new ApiError(error);
  }
  return new ApiError({ detail: "Something went wrong. Please try again.", code: "unknown_error" });
}
