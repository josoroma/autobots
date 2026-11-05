import { NextResponse, type NextRequest } from "next/server";

import { CSRF_COOKIE, CSRF_HEADER, guardRequest } from "@/lib/request-guard";
import { serverConfig } from "@/lib/server-config";
import { sessionClient } from "@/lib/session";

const REFUSED = {
  code: "sign_in_failed",
  message: "That email and password did not work.",
};

function guard(request: NextRequest): NextResponse | null {
  const refusal = guardRequest(
    {
      method: request.method,
      host: request.headers.get("host"),
      origin: request.headers.get("origin"),
      fetchSite: request.headers.get("sec-fetch-site"),
      csrfHeader: request.headers.get(CSRF_HEADER),
      csrfCookie: request.cookies.get(CSRF_COOKIE)?.value ?? null,
    },
    { allowedOrigin: serverConfig().allowedOrigin },
  );
  return refusal === null
    ? null
    : NextResponse.json(
        { code: refusal, message: "This request was refused." },
        { status: 403 },
      );
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  const refused = guard(request);
  if (refused !== null) {
    return refused;
  }
  const body: unknown = await request.json().catch(() => null);
  const { email, password } = (body ?? {}) as {
    email?: unknown;
    password?: unknown;
  };
  if (
    typeof email !== "string" ||
    typeof password !== "string" ||
    email === "" ||
    password === ""
  ) {
    return NextResponse.json(REFUSED, { status: 401 });
  }
  const client = await sessionClient();
  const { error } = await client.auth.signInWithPassword({ email, password });
  if (error !== null) {
    return NextResponse.json(REFUSED, { status: 401 });
  }
  return NextResponse.json({ signed_in: true });
}

export async function DELETE(request: NextRequest): Promise<NextResponse> {
  const refused = guard(request);
  if (refused !== null) {
    return refused;
  }
  const client = await sessionClient();
  await client.auth.signOut({ scope: "local" });
  return NextResponse.json({ signed_in: false });
}
