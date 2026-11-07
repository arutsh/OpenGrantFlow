// Whole amounts stay compact; any fractional part shows both decimals.
export function formatCurrency(amount: number, currencyCode?: string): string {
  const fractionDigits = Number.isInteger(amount) ? 0 : 2;
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: currencyCode || "GBP",
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
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
