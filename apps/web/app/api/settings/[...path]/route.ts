import type { NextRequest, NextResponse } from "next/server";

import { forward } from "@/lib/bff";

type Context = { params: Promise<{ path: string[] }> };

// PRD-Model-Providers MP-05 names these /api/settings endpoints, so they stay beside the /api/v1
// catch-all, and pass the query on the same way (WSHL-16).
async function handle(
  request: NextRequest,
  context: Context,
): Promise<NextResponse> {
  const { path } = await context.params;
  return forward(
    request,
    `/v1/settings/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`,
  );
}

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const DELETE = handle;
