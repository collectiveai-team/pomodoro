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

export const GENERIC_ERROR_MESSAGE = "Algo salió mal. Inténtalo de nuevo.";

/** Spanish text per backend error `code`; the API `detail` is English and never shown. */
const MESSAGES_BY_CODE: Record<string, string> = {
  duplicate_email: "Ya existe una cuenta con ese email.",
  invalid_credentials: "Email o contraseña incorrectos.",
  rate_limited: "Demasiados intentos. Espera un momento e inténtalo de nuevo.",
  invalid_time_zone: "La zona horaria no es válida.",
  invalid_email: "El email no es válido.",
  invalid_password_length: "La contraseña no tiene una longitud válida.",
  validation_error: "Los datos enviados no son válidos.",
  empty_task_text: "El texto de la tarea no puede estar vacío.",
  task_text_too_long: "El texto de la tarea es demasiado largo.",
  duplicate_task_text: "Ya existe una tarea activa con ese texto.",
  task_not_found: "No se encontró la tarea.",
  task_in_use_by_timer: "La tarea está en uso por el Timer.",
  task_has_recorded_pomodoros: "La tarea tiene Pomodoros registrados.",
  task_reorder_mismatch: "El orden de las tareas cambió. Recarga la lista.",
  empty_tag_name: "El nombre de la etiqueta no puede estar vacío.",
  duplicate_tag_name: "Ya existe una etiqueta con ese nombre.",
  tag_not_found: "No se encontró la etiqueta.",
  unknown_error: GENERIC_ERROR_MESSAGE,
};

/** Codes that have a dedicated Spanish message. */
export const MAPPED_ERROR_CODES: readonly string[] = Object.keys(MESSAGES_BY_CODE);

/** Spanish message for an error `code`, falling back to the generic message. */
export function messageForCode(code: string): string {
  return Object.hasOwn(MESSAGES_BY_CODE, code)
    ? (MESSAGES_BY_CODE[code] ?? GENERIC_ERROR_MESSAGE)
    : GENERIC_ERROR_MESSAGE;
}

/** `message` is the Spanish text for `code`; the raw API text stays in `detail`. */
export class ApiError extends Error {
  readonly code: string;
  readonly detail: string;

  constructor(body: ApiErrorBody) {
    super(messageForCode(body.code));
    this.code = body.code;
    this.detail = body.detail;
  }
}

/** Parses any openapi-fetch `error` value into the shared `ErrorResponse` shape. */
export function toApiError(error: unknown): ApiError {
  if (isApiErrorBody(error)) {
    return new ApiError(error);
  }
  return new ApiError({ detail: "Unknown error", code: "unknown_error" });
}
