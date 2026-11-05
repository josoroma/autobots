import type { NextRequest, NextResponse } from "next/server";

import { forward } from "@/lib/bff";

export function GET(request: NextRequest): Promise<NextResponse> {
  return forward(request, "/v1/models");
}
