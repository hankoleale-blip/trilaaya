import { NextRequest, NextResponse } from "next/server";

const COOKIE_NAME = "trikaaya_admin_session";

export function middleware(request: NextRequest) {
  // Allow the Admin login page without authentication.
  if (
    request.nextUrl.pathname === "/admin" ||
    request.nextUrl.pathname === "/admin/"
  ) {
    return NextResponse.next();
  }

  // Check whether the Admin session cookie exists.
  const token = request.cookies.get(COOKIE_NAME)?.value;

  // Redirect users without a session to the Admin login page.
  if (!token) {
    const url = request.nextUrl.clone();
    url.pathname = "/admin";
    url.search = "";

    return NextResponse.redirect(url);
  }

  // Do not call the Render backend from middleware.
  // Backend authentication is handled by the Admin API routes.
  return NextResponse.next();
}

export const config = {
  matcher: ["/admin/:path*"],
};
