import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

import { SUPABASE_ANON_KEY, SUPABASE_URL } from "@/lib/supabase/env";

const PROTECTED_PREFIXES = [
  "/dashboard",
  "/portfolio",
  "/research",
  "/agents",
  "/brokers",
  "/trade-approvals",
  "/reports",
  "/settings",
];

const AUTH_ONLY_PREFIXES = ["/login", "/signup"];

/**
 * Refreshes the Supabase session cookie on every request and enforces the
 * auth boundary described in ARCHITECTURE.md section 4:
 *  - unauthenticated visitors to any app route are sent to /login
 *  - authenticated visitors to /login or /signup are sent to /dashboard
 *
 * Called from the top-level `proxy.ts` (Next.js 16 renamed `middleware.ts`
 * to `proxy.ts`; the exported function below is intentionally framework
 * agnostic so it is easy to unit test).
 */
export async function updateSession(request: NextRequest) {
  let supabaseResponse = NextResponse.next({ request });

  const supabase = createServerClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value }) =>
          request.cookies.set(name, value)
        );
        supabaseResponse = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, value, options }) =>
          supabaseResponse.cookies.set(name, value, options)
        );
      },
    },
  });

  const { data } = await supabase.auth.getUser();
  const user = data.user;
  const { pathname } = request.nextUrl;

  const isProtected = PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
  );
  const isAuthOnly = AUTH_ONLY_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
  );

  if (!user && isProtected) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }

  if (user && isAuthOnly) {
    const url = request.nextUrl.clone();
    url.pathname = "/dashboard";
    url.search = "";
    return NextResponse.redirect(url);
  }

  return supabaseResponse;
}
