import { z } from "zod";

export const createPortfolioSchema = z.object({
  name: z.string().min(1, "Give your portfolio a name.").max(80),
  base_currency: z.string().min(1, "Pick a base currency."),
});

export type CreatePortfolioValues = z.infer<typeof createPortfolioSchema>;

export const CURRENCIES = ["INR", "USD", "EUR", "GBP"] as const;
