/**
 * Centralized Supabase env lookup with safe fallbacks. Falling back to a
 * syntactically valid (but non-functional) URL/key means a missing
 * .env.local never crashes the build or the app shell — auth calls will
 * simply fail gracefully (network/401 errors) instead of throwing at
 * client construction time.
 */
export const SUPABASE_URL =
  process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_URL.trim().length > 0
    ? process.env.NEXT_PUBLIC_SUPABASE_URL
    : "https://placeholder.supabase.co";

export const SUPABASE_ANON_KEY =
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY &&
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY.trim().length > 0
    ? process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
    : "placeholder-anon-key";
