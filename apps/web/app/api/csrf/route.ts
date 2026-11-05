import { randomBytes } from "node:crypto";

import { NextResponse } from "next/server";

import { CSRF_COOKIE, CSRF_HEADER } from "@/lib/request-guard";

// A double-submit token. It is readable by this origin's script on purpose, and is no credential.
export function GET(): NextResponse {
  const token = randomBytes(32).toString("base64url");
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
