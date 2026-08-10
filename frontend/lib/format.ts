/** Shared financial-figure formatting so every page renders numbers identically. */

export function formatCurrency(value: number, currency = "INR"): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: Math.abs(value) >= 1000 ? 0 : 2,
  }).format(value);
}

export function formatNumber(value: number, maximumFractionDigits = 2): string {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits }).format(value);
}

/**
 * `Number.prototype.toFixed` ignores the requested precision and falls back
 * to exponential notation ("2.8e+277") once `|value| >= 1e21` — a real case
 * for CAGR, whose exponent blows up on a portfolio with a very short
 * transaction history. Cap the display at a large-but-readable bound rather
 * than ever rendering scientific notation in the UI.
 */
const PERCENT_DISPLAY_CAP = 999_999;

export function formatPercent(value: number, maximumFractionDigits = 2): string {
  if (!Number.isFinite(value)) return "—";
  if (Math.abs(value) > PERCENT_DISPLAY_CAP) {
    return value > 0 ? `>${PERCENT_DISPLAY_CAP.toLocaleString()}%` : `<-${PERCENT_DISPLAY_CAP.toLocaleString()}%`;
  }
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(maximumFractionDigits)}%`;
}

export function formatDate(value: string | Date): string {
  const date = typeof value === "string" ? new Date(value) : value;
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
  }).format(date);
}

export function formatDateTime(value: string | Date): string {
  const date = typeof value === "string" ? new Date(value) : value;
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

/**
 * Tailwind classes for the red/green gain-loss convention used across every
 * financial figure. Always pair the two so the color survives theme
 * switches (tokens defined in app/globals.css: --gain / --loss).
 */
export function gainLossClass(value: number): string {
  if (value > 0) return "text-gain";
  if (value < 0) return "text-loss";
  return "text-muted-foreground";
}

export function signedCurrency(value: number, currency = "INR"): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${formatCurrency(value, currency)}`;
}
