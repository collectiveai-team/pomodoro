import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const DEFAULT_BACKEND_ORIGIN = "http://127.0.0.1:8000";

export function proxy(request: NextRequest) {
  const backendOrigin = process.env.BACKEND_ORIGIN ?? DEFAULT_BACKEND_ORIGIN;
  const destination = new URL(
    `${request.nextUrl.pathname}${request.nextUrl.search}`,
    backendOrigin,
  );
  return NextResponse.rewrite(destination);
}

export const config = {
  matcher: "/api/:path*",
};
