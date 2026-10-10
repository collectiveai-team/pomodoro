import { apiClient } from "./api-client";
import { toApiError } from "./api-error";

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
