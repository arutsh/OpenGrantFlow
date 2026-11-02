// No canonical currency list exists elsewhere in this codebase (budgets.tsx's
// currency filter derives its options from budgets that already exist, which
// doesn't help when there's nothing to derive from yet, e.g. picking a
// budget's actual_currency for the first time). A fixed, modest list is good
// enough for the currency-ledger UI; broaden if a real need shows up.
export const CURRENCY_CODES = [
  "GBP",
  "USD",
  "EUR",
  "AMD",
  "KES",
  "UGX",
  "TZS",
  "NGN",
  "ZAR",
  "INR",
  "AUD",
  "CAD",
];

export function formatCurrency(amount: number, currencyCode?: string): string {
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: currencyCode || "GBP",
    maximumFractionDigits: 0,
  }).format(amount);
}

// A donor can fund budgets in more than one currency, so totals must not be
// blended into a single number under one currency — render each currency's
// total separately, joined by a bullet rather than "+" (a "+" reads as
// arithmetic, implying the figures could be summed into one number).
export function formatCurrencyAmounts(
  amounts: { currency?: string; total_allocated: number }[],
): string {
  if (amounts.length === 0) return formatCurrency(0);
  return amounts
    .map((a) => formatCurrency(a.total_allocated, a.currency))
    .join(" · ");
}
