import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
const COOKIE_NAME = "trikaaya_admin_session";

export async function GET(request: NextRequest) {
  const token = request.cookies.get(COOKIE_NAME)?.value;
  if (!token) return NextResponse.json({ detail: "Admin sign-in is required." }, { status: 401, headers: { "Cache-Control": "no-store" } });
  try {
    const upstream = await fetch(`${API_URL}/admin/auth/me`, {
      headers: { cookie: `${COOKIE_NAME}=${token}` },
      cache: "no-store",
    });
    const data = await upstream.json().catch(() => ({ detail: "Unable to verify Admin session." }));
    return NextResponse.json(data, { status: upstream.status, headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ detail: "Admin service is unavailable." }, { status: 503, headers: { "Cache-Control": "no-store" } });
  }
}
