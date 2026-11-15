import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
const COOKIE_NAME = "trikaaya_admin_session";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const upstream = await fetch(`${API_URL}/admin/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(request.headers.get("origin") ? { Origin: request.headers.get("origin") as string } : {}) },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    const data = await upstream.json().catch(() => ({}));
    if (!upstream.ok) return NextResponse.json(data, { status: upstream.status, headers: { "Cache-Control": "no-store" } });

    const upstreamHeaders = upstream.headers as Headers & { getSetCookie?: () => string[] };
    const setCookies = upstreamHeaders.getSetCookie?.() || [upstream.headers.get("set-cookie") || ""];
    const cookie = setCookies.find((value) => value.startsWith(`${COOKIE_NAME}=`));
    const token = cookie?.match(new RegExp(`^${COOKIE_NAME}=([^;]+)`))?.[1];
    if (!token) return NextResponse.json({ detail: "The authentication service did not issue a session cookie." }, { status: 502 });

    const maxAge = Math.max(300, Math.min(86400, Number(process.env.ADMIN_SESSION_MAX_AGE_SECONDS || 3600)));
    const response = NextResponse.json({ authenticated: true, email: data.email }, { headers: { "Cache-Control": "no-store" } });
    response.cookies.set(COOKIE_NAME, token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge,
    });
    return response;
  } catch {
    return NextResponse.json({ detail: "Admin service is unavailable. Check the backend URL and try again." }, { status: 503, headers: { "Cache-Control": "no-store" } });
  }
}
