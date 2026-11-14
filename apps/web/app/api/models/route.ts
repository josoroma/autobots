import type { NextRequest, NextResponse } from "next/server";

import { forward } from "@/lib/bff";

// PRD-Model-Providers MP-05 names `GET /api/models`, so it stays beside the /api/v1 catch-all.
export function GET(request: NextRequest): Promise<NextResponse> {
  return forward(request, "/v1/models");
}
