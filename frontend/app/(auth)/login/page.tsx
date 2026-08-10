import Link from "next/link";
import type { Metadata } from "next";

import { AuthForm } from "@/components/auth/auth-form";

export const metadata: Metadata = { title: "Sign in" };

export default function LoginPage() {
  return (
    <div className="space-y-7">
      <div className="space-y-1">
        <h1 className="text-[26px] font-medium tracking-[-0.02em] text-foreground">Sign in</h1>
        <p className="text-[13px] text-muted-foreground">Sign in to your FINMIND workspace.</p>
      </div>
      <AuthForm mode="login" />
      <p className="text-center text-[13px] text-muted-foreground">
        No account?{" "}
        <Link href="/signup" className="font-medium text-primary hover:underline">
          Create one
        </Link>
      </p>
    </div>
  );
}
