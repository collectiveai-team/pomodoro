/** Redirects to `/login` on an expired or missing session; the backend is sole authority (ADR-0001). */
export async function redirectToLoginOn401(response: Response): Promise<boolean> {
  if (response.status === 401) {
    window.location.assign("/login");
    return true;
  }
  return false;
}
