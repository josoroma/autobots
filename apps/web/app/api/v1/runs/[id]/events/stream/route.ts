import type { NextRequest } from "next/server";

import { streamFrom } from "@/lib/bff";

type Context = { params: Promise<{ id: string }> };

export async function GET(
  request: NextRequest,
  context: Context,
): Promise<Response> {
  const { id } = await context.params;
  const after = request.nextUrl.searchParams.get("after") ?? "0";
  const cursor = /^\d{1,18}$/.test(after) ? after : "0";
  return streamFrom(
    request,
    `/v1/runs/${encodeURIComponent(id)}/events/stream?after=${cursor}`,
  );
}
