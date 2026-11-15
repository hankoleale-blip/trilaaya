import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
const COOKIE_NAME = "trikaaya_admin_session";

export async function POST(request: NextRequest) {
  const origin = request.headers.get("origin");
  if (origin && origin !== request.nextUrl.origin) {
    return NextResponse.json({ detail: "Request origin is not allowed." }, { status: 403 });
  }
  try {
    const token = request.cookies.get(COOKIE_NAME)?.value;
    if (token) {
      await fetch(`${API_URL}/admin/auth/logout`, {
        method: "POST",
        headers: { cookie: `${COOKIE_NAME}=${token}` },
        cache: "no-store",
      });
    }
  } catch {
    // The local HttpOnly cookie is still cleared. JWT expiry also bounds any copied token.
  }
  const response = NextResponse.json({ authenticated: false }, { headers: { "Cache-Control": "no-store" } });
  response.cookies.set(COOKIE_NAME, "", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });
  return response;
}
