import Link from "next/link";
import type { Metadata } from "next";

import { AuthForm } from "@/components/auth/auth-form";

export const metadata: Metadata = { title: "Create account" };

export default function SignupPage() {
  return (
    <div className="space-y-7">
      <div className="space-y-1">
        <h1 className="text-[26px] font-medium tracking-[-0.02em] text-foreground">
          Create your account
        </h1>
        <p className="text-[13px] text-muted-foreground">
          Start tracking your portfolio with an AI analyst that cites its sources.
        </p>
      </div>
      <AuthForm mode="signup" />
      <p className="text-center text-[13px] text-muted-foreground">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-primary hover:underline">
          Sign in
        </Link>
      </p>
    </div>
  );
}
