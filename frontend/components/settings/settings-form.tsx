"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ApiError, updateMe } from "@/lib/api/client";
import { createClient } from "@/lib/supabase/client";
import { cn } from "@/lib/utils";
import { settingsSchema, type SettingsValues } from "@/lib/validation/settings";
import { CURRENCIES } from "@/lib/validation/portfolio";
import type { UserProfile } from "@/lib/api/types";

const RISK_OPTIONS = [
  { value: "conservative", label: "Conservative" },
  { value: "moderate", label: "Moderate" },
  { value: "aggressive", label: "Aggressive" },
] as const;

export function SettingsForm({ profile }: { profile: UserProfile }) {
  const form = useForm<SettingsValues>({
    resolver: zodResolver(settingsSchema),
    defaultValues: {
      full_name: profile.full_name ?? "",
      risk_tolerance: profile.risk_tolerance ?? "moderate",
      investment_horizon_years: profile.investment_horizon_years ?? undefined,
      base_currency: profile.base_currency ?? "INR",
    },
  });

  async function onSubmit(values: SettingsValues) {
    try {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      await updateMe(data.session?.access_token ?? null, values);
      toast.success("Profile updated.");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not update your profile.");
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Profile</CardTitle>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="max-w-lg space-y-5">
            <FormField
              control={form.control}
              name="full_name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Full name</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="risk_tolerance"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Risk tolerance</FormLabel>
                  <FormControl>
                    <div
                      role="radiogroup"
                      aria-label="Risk tolerance"
                      className="inline-flex w-full rounded-lg bg-background p-[3px] shadow-[inset_0_0_0_1px_var(--border)]"
                    >
                      {RISK_OPTIONS.map((option) => {
                        const active = field.value === option.value;
                        return (
                          <button
                            key={option.value}
                            type="button"
                            role="radio"
                            aria-checked={active}
                            onClick={() => field.onChange(option.value)}
                            className={cn(
                              "flex-1 rounded-[calc(var(--radius-lg)-3px)] px-3 py-1.5 text-[13px] font-medium transition-colors",
                              active
                                ? "text-primary shadow-[inset_0_0_0_1px_var(--primary)]"
                                : "text-muted-foreground hover:text-foreground"
                            )}
                          >
                            {option.label}
                          </button>
                        );
                      })}
                    </div>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField
                control={form.control}
                name="investment_horizon_years"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Investment horizon (years)</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        min={0}
                        max={100}
                        placeholder="e.g. 5"
                        value={field.value ?? ""}
                        onChange={(e) => field.onChange(e.target.value === "" ? undefined : Number(e.target.value))}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="base_currency"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Base currency</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {CURRENCIES.map((currency) => (
                          <SelectItem key={currency} value={currency}>
                            {currency}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <div className="flex items-center gap-2 pt-1">
              <Button type="submit" variant="accent-outline" disabled={form.formState.isSubmitting}>
                {form.formState.isSubmitting && <Loader2 className="size-4 animate-spin" />}
                Save changes
              </Button>
              <Button
                type="button"
                variant="outline"
                disabled={form.formState.isSubmitting}
                onClick={() => form.reset()}
              >
                Discard
              </Button>
            </div>
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}
