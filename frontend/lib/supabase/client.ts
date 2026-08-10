import { createBrowserClient } from "@supabase/ssr";

import { SUPABASE_ANON_KEY, SUPABASE_URL } from "@/lib/supabase/env";

/**
 * Browser-side Supabase client. Safe to call multiple times — each call
 * returns a client bound to the public (anon) key, relying on RLS for
 * authorization. Use inside Client Components only.
 */
export function createClient() {
  return createBrowserClient(SUPABASE_URL, SUPABASE_ANON_KEY);
}
