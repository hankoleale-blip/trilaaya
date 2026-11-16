import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const API_URL = (
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
).replace(/\/$/, "");

const COOKIE_NAME = "trikaaya_admin_session";

async function proxy(
  request: NextRequest,
  context: { params: { path: string[] } }
) {
  const token = request.cookies.get(COOKIE_NAME)?.value;

  if (!token) {
    return NextResponse.json(
      { detail: "Admin sign-in is required." },
      { status: 401 }
    );
  }

  const path = (context.params.path || [])
    .map(encodeURIComponent)
    .join("/");

  const url = `${API_URL}/admin/${path}${request.nextUrl.search}`;

  const headers = new Headers();
  headers.set("cookie", `${COOKIE_NAME}=${token}`);

  const contentType = request.headers.get("content-type");
  if (contentType) {
    headers.set("content-type", contentType);
  }

  const body = ["GET", "HEAD"].includes(request.method)
    ? undefined
    : await request.arrayBuffer();

  try {
    const upstream = await fetch(url, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
    });

    const type =
      upstream.headers.get("content-type") || "application/json";

    return new NextResponse(await upstream.arrayBuffer(), {
      status: upstream.status,
      headers: {
        "content-type": type,
        "cache-control": "no-store",
      },
    });
  } catch {
    return NextResponse.json(
      { detail: "Admin API is unavailable." },
      { status: 503 }
    );
  }
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const PUT = proxy;
export const DELETE = proxy;
