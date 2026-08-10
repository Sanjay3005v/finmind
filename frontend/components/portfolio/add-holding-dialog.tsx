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
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { createHolding, ApiError } from "@/lib/api/client";
import { ASSET_CLASSES, type AssetClass } from "@/lib/api/types";
import { createClient } from "@/lib/supabase/client";
import { ASSET_CLASS_LABELS, createHoldingSchema, type CreateHoldingValues } from "@/lib/validation/holding";

interface AddHoldingDialogProps {
  portfolioId: string;
  trigger?: React.ReactNode;
}

/** Manually records any holding — the only way to track an asset with no
 * broker adapter (gold, silver, or anything outside the four supported
 * brokers). Deliberately plain styling; visual design is being redone
 * separately — this is here for the data path, not the look. */
export function AddHoldingDialog({ portfolioId, trigger }: AddHoldingDialogProps) {
  const router = useRouter();
  const [open, setOpen] = React.useState(false);

  const form = useForm<CreateHoldingValues>({
    resolver: zodResolver(createHoldingSchema),
    defaultValues: {
      symbol: "",
      exchange: "NSE",
      quantity: undefined,
      avg_price: undefined,
      current_price: undefined,
      asset_class: "equity",
      sector: "",
    },
  });

  async function onSubmit(values: CreateHoldingValues) {
    try {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      await createHolding(data.session?.access_token ?? null, portfolioId, {
        ...values,
        asset_class: values.asset_class as AssetClass,
        sector: values.sector || undefined,
      });
      toast.success(`${values.symbol.toUpperCase()} added.`);
      form.reset();
      setOpen(false);
      router.refresh();
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Could not add this holding. Please try again.";
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
          <Button size="sm" variant="accent-outline">
            <PlusCircle className="size-4" />
            Add holding
          </Button>
        )}
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add a holding</DialogTitle>
          <DialogDescription>
            Manually record any asset — a stock, gold, silver, crypto, anything with no connected
            broker. Symbol + exchange must be unique in this portfolio.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <FormField
                control={form.control}
                name="symbol"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Symbol</FormLabel>
                    <FormControl>
                      <Input placeholder="GOLD" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="exchange"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Exchange</FormLabel>
                    <FormControl>
                      <Input placeholder="MCX" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={form.control}
              name="asset_class"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Asset class</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {ASSET_CLASSES.map((ac) => (
                        <SelectItem key={ac} value={ac}>
                          {ASSET_CLASS_LABELS[ac] ?? ac}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="grid grid-cols-3 gap-3">
              <FormField
                control={form.control}
                name="quantity"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Quantity</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        step="any"
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
                name="avg_price"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Avg. price</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        step="any"
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
                name="current_price"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Current price</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        step="any"
                        placeholder="optional"
                        value={field.value ?? ""}
                        onChange={(e) => field.onChange(e.target.value === "" ? undefined : Number(e.target.value))}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={form.control}
              name="sector"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Sector (optional)</FormLabel>
                  <FormControl>
                    <Input placeholder="Precious metals" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <DialogFooter>
              <Button type="submit" variant="accent-outline" disabled={form.formState.isSubmitting}>
                {form.formState.isSubmitting && <Loader2 className="size-4 animate-spin" />}
                Add holding
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
