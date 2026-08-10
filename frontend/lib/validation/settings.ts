import { z } from "zod";

export const settingsSchema = z.object({
  full_name: z.string().max(120).optional(),
  risk_tolerance: z.enum(["conservative", "moderate", "aggressive"]),
  investment_horizon_years: z.number().int().min(0).max(100).optional(),
  base_currency: z.string().min(1, "Pick a base currency."),
});

export type SettingsValues = z.infer<typeof settingsSchema>;
