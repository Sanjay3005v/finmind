import type { NextRequest } from "next/server";
import { updateSession } from "@/lib/supabase/proxy";

// Next.js 16 renamed the `middleware.ts` file convention to `proxy.ts`
// (same runtime behavior, see node_modules/next/dist/docs .../proxy.md).
// This is the single source of truth for session refresh + route guarding.
export function proxy(request: NextRequest) {
  return updateSession(request);
}

export const config = {
  matcher: [
    /*
     * Run on every route except static assets and image optimization
     * files, so the Supabase session cookie is refreshed everywhere.
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
