"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { createClient } from "@/lib/supabase/client";
import {
  loginSchema,
  signupSchema,
  type LoginValues,
  type SignupValues,
} from "@/lib/validation/auth";

type AuthFormProps =
  | { mode: "login"; children?: React.ReactNode }
  | { mode: "signup"; children?: React.ReactNode };

function friendlyAuthError(message: string): string {
  const normalized = message.toLowerCase();
  if (normalized.includes("invalid login credentials")) {
    return "Invalid email or password. Please try again.";
  }
  if (normalized.includes("already registered") || normalized.includes("already exists")) {
    return "An account with this email already exists. Try signing in instead.";
  }
  if (normalized.includes("fetch") || normalized.includes("network")) {
    return "Network error — could not reach the authentication server. Check your connection and try again.";
  }
  return message;
}

/**
 * Shared email/password auth form for /login and /signup. Deliberately
 * structured so an OAuth provider button can be dropped in later via
 * `children` (rendered below the submit button, after a divider) without
 * touching validation/submit logic — no fabricated OAuth buttons for now
 * since no provider is configured yet.
 */
export function AuthForm({ mode, children }: AuthFormProps) {
  const router = useRouter();
  const [formError, setFormError] = React.useState<string | null>(null);

  const loginForm = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const signupForm = useForm<SignupValues>({
    resolver: zodResolver(signupSchema),
    defaultValues: { fullName: "", email: "", password: "", confirmPassword: "" },
  });

  const isLogin = mode === "login";
  const form = isLogin ? loginForm : signupForm;
  const isSubmitting = form.formState.isSubmitting;

  async function onSubmitLogin(values: LoginValues) {
    setFormError(null);
    try {
      const supabase = createClient();
      const { error } = await supabase.auth.signInWithPassword({
        email: values.email,
        password: values.password,
      });
      if (error) {
        setFormError(friendlyAuthError(error.message));
        return;
      }
      router.push("/dashboard");
      router.refresh();
    } catch (err) {
      setFormError(
        friendlyAuthError(err instanceof Error ? err.message : "Network error.")
      );
    }
  }

  async function onSubmitSignup(values: SignupValues) {
    setFormError(null);
    try {
      const supabase = createClient();
      const { error } = await supabase.auth.signUp({
        email: values.email,
        password: values.password,
        options: { data: { full_name: values.fullName } },
      });
      if (error) {
        setFormError(friendlyAuthError(error.message));
        return;
      }
      router.push("/dashboard");
      router.refresh();
    } catch (err) {
      setFormError(
        friendlyAuthError(err instanceof Error ? err.message : "Network error.")
      );
    }
  }

  if (isLogin) {
    return (
      <Form {...loginForm}>
        <form onSubmit={loginForm.handleSubmit(onSubmitLogin)} className="space-y-4">
          {formError ? (
            <Alert variant="destructive">
              <AlertDescription>{formError}</AlertDescription>
            </Alert>
          ) : null}
          <FormField
            control={loginForm.control}
            name="email"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Email</FormLabel>
                <FormControl>
                  <Input type="email" autoComplete="email" placeholder="you@company.com" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={loginForm.control}
            name="password"
            render={({ field }) => (
              <FormItem>
                <div className="flex items-center justify-between">
                  <FormLabel>Password</FormLabel>
                  <Link href="#" className="text-xs text-muted-foreground hover:text-primary">
                    Forgot password?
                  </Link>
                </div>
                <FormControl>
                  <Input type="password" autoComplete="current-password" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <Button
            type="submit"
            className="h-[42px] w-full bg-[var(--accent-400)] text-background hover:bg-[var(--accent-300)]"
            disabled={isSubmitting}
          >
            {isSubmitting && <Loader2 className="size-4 animate-spin" />}
            Sign in
          </Button>
          {children}
        </form>
      </Form>
    );
  }

  return (
    <Form {...signupForm}>
      <form onSubmit={signupForm.handleSubmit(onSubmitSignup)} className="space-y-4">
        {formError ? (
          <Alert variant="destructive">
            <AlertDescription>{formError}</AlertDescription>
          </Alert>
        ) : null}
        <FormField
          control={signupForm.control}
          name="fullName"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Full name</FormLabel>
              <FormControl>
                <Input autoComplete="name" placeholder="Jane Investor" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={signupForm.control}
          name="email"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Email</FormLabel>
              <FormControl>
                <Input type="email" autoComplete="email" placeholder="you@company.com" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={signupForm.control}
          name="password"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Password</FormLabel>
              <FormControl>
                <Input type="password" autoComplete="new-password" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={signupForm.control}
          name="confirmPassword"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Confirm password</FormLabel>
              <FormControl>
                <Input type="password" autoComplete="new-password" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting && <Loader2 className="size-4 animate-spin" />}
          Create account
        </Button>
        {children}
      </form>
    </Form>
  );
}
