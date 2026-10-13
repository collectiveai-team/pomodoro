import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { GENERIC_ERROR_MESSAGE, MAPPED_ERROR_CODES, messageForCode, toApiError } from "./api-error";

const BACKEND_APP = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../backend/pomodoro/entrypoints/app.py",
);

/** Error codes the backend emits as an `ErrorResponse`, read from its app factory source. */
function backendErrorCodes(): string[] {
  const source = readFileSync(BACKEND_APP, "utf8");
  const codes = new Set<string>();
  for (const match of source.matchAll(/\(\w+Error, \d{3}, "(\w+)"\)/g)) {
    codes.add(match[1] as string);
  }
  for (const match of source.matchAll(/_error_response\(\s*[^,]+,\s*[^,]+,\s*"(\w+)"\)/g)) {
    codes.add(match[1] as string);
  }
  return [...codes];
}

// Emitted by the backend but deliberately left to the generic Spanish message.
const UNMAPPED_BACKEND_CODES = ["http_error", "internal_error"];

const KNOWN_CODES = backendErrorCodes().filter((code) => !UNMAPPED_BACKEND_CODES.includes(code));

describe("messageForCode", () => {
  it.each(KNOWN_CODES)("maps %s to a specific Spanish message", (code) => {
    const message = messageForCode(code);
    expect(message).not.toBe(GENERIC_ERROR_MESSAGE);
    expect(message).toMatch(/[a-záéíóúñ]/i);
  });

  it("finds the codes the backend emits", () => {
    expect(KNOWN_CODES).toContain("validation_error");
    expect(KNOWN_CODES).toContain("duplicate_email");
    expect(KNOWN_CODES.length).toBeGreaterThan(10);
  });

  it("maps only codes the backend really emits", () => {
    const emitted = [...backendErrorCodes(), "unknown_error"];
    expect(MAPPED_ERROR_CODES.filter((code) => !emitted.includes(code))).toEqual([]);
  });

  it.each(UNMAPPED_BACKEND_CODES)("falls back to generic for backend code %s", (code) => {
    expect(messageForCode(code)).toBe(GENERIC_ERROR_MESSAGE);
  });

  it.each(["unknown_error", "something_new", "toString"])(
    "falls back to generic for %s",
    (code) => {
      expect(messageForCode(code)).toBe(GENERIC_ERROR_MESSAGE);
    },
  );
});

describe("toApiError", () => {
  it("uses the Spanish text and keeps the English detail aside", () => {
    const error = toApiError({ detail: "Email taken", code: "duplicate_email" });
    expect(error.message).toBe("Ya existe una cuenta con ese email.");
    expect(error.detail).toBe("Email taken");
    expect(error.code).toBe("duplicate_email");
  });

  it("shows the Spanish validation text for a 422 validation_error body", () => {
    const error = toApiError({ detail: "Invalid request.", code: "validation_error" });
    expect(error.message).toBe("Los datos enviados no son válidos.");
  });

  it("turns a malformed body into the generic Spanish message", () => {
    const error = toApiError({ nope: true });
    expect(error.code).toBe("unknown_error");
    expect(error.message).toBe(GENERIC_ERROR_MESSAGE);
  });
});
