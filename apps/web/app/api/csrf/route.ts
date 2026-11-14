import { randomBytes } from "node:crypto";

import { NextResponse, type NextRequest } from "next/server";

import { CSRF_COOKIE, CSRF_HEADER } from "@/lib/request-guard";

// What this route mints: 32 random bytes, base64url.
const TOKEN = /^[A-Za-z0-9_-]{43}$/;

// A double-submit token. It is readable by this origin's script on purpose, and is no credential.
// R-19: one per browser session. The cookie's token is returned while it's well formed, so writes
// that overlap can't refuse each other by minting over one another's token.
export function GET(request: NextRequest): NextResponse {
  const existing = request.cookies.get(CSRF_COOKIE)?.value;
  const token =
    existing !== undefined && TOKEN.test(existing)
      ? existing
      : randomBytes(32).toString("base64url");
  const response = NextResponse.json({ header: CSRF_HEADER, token });
  response.cookies.set(CSRF_COOKIE, token, {
    sameSite: "strict",
    path: "/",
    httpOnly: false,
    secure: false,
  });
  response.headers.set("Cache-Control", "no-store");
  return response;
}
