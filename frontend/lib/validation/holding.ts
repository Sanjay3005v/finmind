import { z } from "zod";

import { ASSET_CLASSES } from "@/lib/api/types";

export const createHoldingSchema = z.object({
  symbol: z.string().min(1, "Symbol is required.").max(40),
  exchange: z.string().min(1, "Exchange is required.").max(20),
  quantity: z.number({ message: "Quantity is required." }).gt(0, "Quantity must be positive."),
  avg_price: z.number({ message: "Average price is required." }).gt(0, "Average price must be positive."),
  current_price: z.number().gt(0).optional(),
  asset_class: z.enum(ASSET_CLASSES as unknown as [string, ...string[]]),
  sector: z.string().max(100).optional(),
});

export type CreateHoldingValues = z.infer<typeof createHoldingSchema>;

export const ASSET_CLASS_LABELS: Record<string, string> = {
  equity: "Equity",
  etf: "ETF",
  mutual_fund: "Mutual fund",
  bond: "Bond",
  cash: "Cash",
  commodity: "Commodity (gold, silver, ...)",
  crypto: "Crypto",
};
