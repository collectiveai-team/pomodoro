import { vi } from "vitest";

export const getMock = vi.fn();
export const postMock = vi.fn();
export const patchMock = vi.fn();
export const deleteMock = vi.fn();

/** Module shape for `vi.mock("@/lib/api-client", ...)`: every verb forwards to its shared mock. */
export const apiClientModule = {
  apiClient: {
    GET: (...args: unknown[]) => getMock(...args),
    POST: (...args: unknown[]) => postMock(...args),
    PATCH: (...args: unknown[]) => patchMock(...args),
    DELETE: (...args: unknown[]) => deleteMock(...args),
  },
};
