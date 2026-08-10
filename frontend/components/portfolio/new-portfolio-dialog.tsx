"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2, PlusCircle } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
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
import { createPortfolio, ApiError } from "@/lib/api/client";
import { createClient } from "@/lib/supabase/client";
import { CURRENCIES, createPortfolioSchema, type CreatePortfolioValues } from "@/lib/validation/portfolio";

interface NewPortfolioDialogProps {
  trigger?: React.ReactNode;
}

export function NewPortfolioDialog({ trigger }: NewPortfolioDialogProps) {
  const router = useRouter();
  const [open, setOpen] = React.useState(false);

  const form = useForm<CreatePortfolioValues>({
    resolver: zodResolver(createPortfolioSchema),
    defaultValues: { name: "", base_currency: "INR" },
  });

  async function onSubmit(values: CreatePortfolioValues) {
    try {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      const accessToken = data.session?.access_token ?? null;

      await createPortfolio(accessToken, values);
      toast.success(`"${values.name}" created.`);
      form.reset();
      setOpen(false);
      router.refresh();
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Could not create the portfolio. Please try again.";
      toast.error(message);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) form.reset();
      }}
    >
      <DialogTrigger asChild>
        {trigger ?? (
          <Button variant="accent-outline">
            <PlusCircle className="size-4" />
            New portfolio
          </Button>
        )}
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create a portfolio</DialogTitle>
          <DialogDescription>
            Portfolios group holdings, transactions, and performance under one base currency.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Name</FormLabel>
                  <FormControl>
                    <Input placeholder="Core Growth" {...field} />
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
                  <Select onValueChange={field.onChange} defaultValue={field.value}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Select a currency" />
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
            <DialogFooter>
              <Button type="submit" variant="accent-outline" disabled={form.formState.isSubmitting}>
                {form.formState.isSubmitting && <Loader2 className="size-4 animate-spin" />}
                Create portfolio
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
