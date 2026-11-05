import type { NextRequest, NextResponse } from "next/server";

import { forward } from "@/lib/bff";

type Context = { params: Promise<{ path: string[] }> };

async function handle(
  request: NextRequest,
  context: Context,
): Promise<NextResponse> {
  const { path } = await context.params;
  // Queries like a replay cursor have to reach the API too.
  return forward(
    request,
    `/v1/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`,
  );
}

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
