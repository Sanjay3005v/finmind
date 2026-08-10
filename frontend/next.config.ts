import type { NextConfig } from "next";

// "standalone" produces the minimal self-contained server bundle the
// Dockerfile expects for self-hosting — but it conflicts with Vercel's own
// build output tracing (ENOENT on next-server.js.nft.json), so skip it
// there; Vercel sets VERCEL=1 on every build.
const nextConfig: NextConfig = {
  output: process.env.VERCEL ? undefined : "standalone",
};

export default nextConfig;
