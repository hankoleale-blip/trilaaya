import { NextRequest, NextResponse } from "next/server";

const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
const COOKIE_NAME = "trikaaya_admin_session";

export async function middleware(request: NextRequest) {
  // /admin is the public login page; every nested Admin route requires a valid session.
  if (request.nextUrl.pathname === "/admin" || request.nextUrl.pathname === "/admin/") {
    return NextResponse.next();
  }
  const token = request.cookies.get(COOKIE_NAME)?.value;
  if (!token) return redirectToLogin(request);

  try {
    const response = await fetch(`${API_URL}/admin/auth/me`, {
      headers: { cookie: `${COOKIE_NAME}=${token}` },
      cache: "no-store",
    });
    if (response.ok) return NextResponse.next();
  } catch {
    // Fail closed: protected Admin pages are unavailable when session validation cannot be reached.
  }
  return redirectToLogin(request);
}

function redirectToLogin(request: NextRequest) {
  const url = request.nextUrl.clone();
  url.pathname = "/admin";
  url.search = "";
  return NextResponse.redirect(url);
}

export const config = { matcher: ["/admin/:path*"] };
