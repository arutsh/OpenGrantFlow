import { useQuery } from "@tanstack/react-query";
import { formatCurrency, formatCurrencyAmounts } from "@/utils/currency";
import { StatusBadge } from "@/pages/Budgets/components/BudgetViewHeader";
import { SectionHead } from "@/components/ui/SectionHead";
import { LinkButton } from "@/components/ui/LinkButton";
import {
  getFundedBudgetsSummary,
  getFundedGrantees,
  getFundedBudgets,
  GranteeSummary,
  FundedBudgetListItem,
} from "@/api/donorDashboardApi";

// Cycled deterministically per grantee row as an avatar mnemonic — not a
// legend-bearing categorical encoding, so reuse past the 4th entry is fine.
const AVATAR_COLORS = [
  "bg-slate-700",
  "bg-teal-600",
  "bg-amber-500",
  "bg-indigo-500",
  "bg-rose-500",
  "bg-cyan-600",
];

function initials(name?: string): string {
  if (!name) return "—";
  const parts = name.trim().split(/\s+/).slice(0, 2);
  return parts.map((p) => p[0]?.toUpperCase() ?? "").join("") || "—";
}

// Converts the real, line-derived local total into the donor's own currency
// — total_amount ÷ estimated_exchange_rate — never the flat donor_total_amount
// promise, which can overstate what's actually been built into budget lines.
// Same "exclude/derive, don't misrepresent" rule as the backend aggregate
// (budget_crud.get_funded_budgets_summary) and the single-budget view
// (BudgetViewSummary.tsx). null when there's no usable rate to convert with.
function donorCurrencyTotal(budget: FundedBudgetListItem): number | null {
  if (
    budget.total_amount == null ||
    !budget.actual_currency ||
    !budget.estimated_exchange_rate
  ) {
    return null;
  }
  return budget.total_amount / budget.estimated_exchange_rate;
}

// Three figures per budget: the donor-currency total (primary — what this
// budget is really worth to the donor), the real local total it was
// converted from, and the rate used, so the conversion is never opaque.
function BudgetAmountCells({ budget }: { budget: FundedBudgetListItem }) {
  const converted = donorCurrencyTotal(budget);
  return (
    <>
      <td className="px-4 py-2.5 text-right text-sm font-semibold text-slate-900 tabular-nums">
        {converted != null ? formatCurrency(converted, budget.actual_currency) : "—"}
      </td>
      <td className="px-4 py-2.5 text-right text-sm text-slate-600 tabular-nums">
        {budget.total_amount != null
          ? formatCurrency(budget.total_amount, budget.local_currency)
          : "—"}
      </td>
      <td className="px-4 py-2.5 text-right text-sm text-slate-500 tabular-nums">
        {budget.estimated_exchange_rate ?? "—"}
      </td>
    </>
  );
}

// Compact mobile-row counterpart to BudgetAmountCells — same three figures
// (donor-currency total, real local total, rate), read as one right-aligned
// stack instead of a labeled 3-column grid, so a budget reads as a single
// scannable list row rather than a card.
function BudgetAmountInline({ budget }: { budget: FundedBudgetListItem }) {
  const converted = donorCurrencyTotal(budget);
  return (
    <div className="text-right flex-shrink-0">
      <div className="text-sm font-semibold text-slate-900 tabular-nums">
        {converted != null ? formatCurrency(converted, budget.actual_currency) : "—"}
      </div>
      <div className="text-[10px] text-slate-400 tabular-nums">
        <span>
          {budget.total_amount != null
            ? formatCurrency(budget.total_amount, budget.local_currency)
            : "—"}
        </span>
        {" · rate "}
        <span>{budget.estimated_exchange_rate ?? "—"}</span>
      </div>
    </div>
  );
}

function GranteeCard({ grantee, colorClass }: { grantee: GranteeSummary; colorClass: string }) {
  return (
    <div className="w-64 flex-shrink-0 snap-start sm:w-auto sm:flex-shrink sm:snap-align-none bg-white rounded-xl border border-slate-200 shadow-sm p-4 flex flex-col gap-3">
      <div className="flex items-center gap-3">
        <div
          className={`w-9 h-9 rounded-lg flex items-center justify-center text-white font-bold text-xs flex-shrink-0 ${colorClass}`}
        >
          {initials(grantee.name)}
        </div>
        <div className="min-w-0">
          <div className="font-semibold text-sm text-slate-900 truncate">
            {grantee.name ?? "—"}
          </div>
          {grantee.country && (
            <div className="text-xs text-slate-500">{grantee.country}</div>
          )}
        </div>
      </div>
      <div className="flex items-baseline justify-between pt-2 border-t border-dashed border-slate-200">
        <span className="font-semibold text-sm tabular-nums text-slate-900">
          {grantee.total_allocated_by_currency.length === 0 ? (
            <span className="font-normal text-slate-400">No committed total yet</span>
          ) : (
            formatCurrencyAmounts(grantee.total_allocated_by_currency)
          )}
        </span>
        <span className="text-[10px] uppercase tracking-wide text-slate-400 flex-shrink-0">
          {grantee.budgets_count} {grantee.budgets_count === 1 ? "budget" : "budgets"}
        </span>
      </div>
    </div>
  );
}

function BudgetActions({ budgetId }: { budgetId: string }) {
  return (
    <>
      <LinkButton to={`/budgets/${budgetId}`} className="flex-1 sm:flex-initial">
        View Budget
      </LinkButton>
      <LinkButton to={`/budgets/${budgetId}/reports`} className="flex-1 sm:flex-initial">
        View Reports
      </LinkButton>
    </>
  );
}

export default function DonorDashboard() {
  const summaryQuery = useQuery({
    queryKey: ["donorDashboard", "summary"],
    queryFn: getFundedBudgetsSummary,
  });
  const granteesQuery = useQuery({
    queryKey: ["donorDashboard", "grantees"],
    queryFn: getFundedGrantees,
  });
  const budgetsQuery = useQuery({
    queryKey: ["donorDashboard", "budgets"],
    queryFn: getFundedBudgets,
  });

  if (
    summaryQuery.isPending ||
    granteesQuery.isPending ||
    budgetsQuery.isPending
  ) {
    return <div>Loading...</div>;
  }

  if (summaryQuery.isError || granteesQuery.isError || budgetsQuery.isError) {
    return <div>Error loading donor dashboard.</div>;
  }

  const summary = summaryQuery.data;
  const grantees = granteesQuery.data ?? [];
  const budgets = budgetsQuery.data ?? [];
  const hasFundedBudgets = budgets.length > 0;
  // The Funded Budgets table only makes sense to act on once a budget is
  // confirmed (a draft's totals/commitment can still change) — same
  // "confirmed only" scope as total_allocated_by_currency backend-side.
  const confirmedBudgets = budgets.filter((b) => b.status === "confirmed");

  // How many CONFIRMED budgets contribute to each actual_currency total —
  // total_allocated_by_currency is grouped (and summed from total_amount ÷
  // estimated_exchange_rate) the same way backend-side, so this stays
  // consistent; a budget missing actual_currency or a usable rate is
  // excluded here too, same as it is from the aggregate itself.
  // Donors only see what a grantee has confirmed, so grantee cards and the
  // headline counts follow the same confirmed-only scope as the table below.
  // Names fall back to the budget's owner name, which the funded budgets list
  // already resolves correctly (the grantees endpoint can return null names).
  const confirmedByOwner = new Map<string, { name?: string; count: number }>();
  confirmedBudgets.forEach((b) => {
    const ownerId = b.owner?.id;
    if (!ownerId) return;
    const entry = confirmedByOwner.get(ownerId) ?? { name: b.owner?.name, count: 0 };
    entry.count += 1;
    confirmedByOwner.set(ownerId, entry);
  });
  const visibleGrantees: GranteeSummary[] = grantees
    .filter((g) => g.id != null && confirmedByOwner.has(String(g.id)))
    .map((g) => {
      const entry = confirmedByOwner.get(String(g.id))!;
      return { ...g, name: g.name ?? entry.name, budgets_count: entry.count };
    });

  const budgetsPerCurrency = new Map<string, number>();
  confirmedBudgets.forEach((b) => {
    if (b.actual_currency && b.estimated_exchange_rate) {
      budgetsPerCurrency.set(
        b.actual_currency,
        (budgetsPerCurrency.get(b.actual_currency) ?? 0) + 1,
      );
    }
  });

  return (
    <div className="flex flex-col">
      {/* Portfolio summary — allocations kept explicitly per-currency, never
          blended into one misleading figure (the mixed-currency fix). */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 to-slate-700 text-white px-8 py-7 mb-10 shadow-lg">
        <div
          aria-hidden="true"
          className="absolute inset-0 opacity-[0.07] pointer-events-none"
          style={{
            backgroundImage:
              "repeating-linear-gradient(to bottom, white 0 1px, transparent 1px 30px)",
            maskImage: "linear-gradient(to bottom, black, transparent 85%)",
            WebkitMaskImage: "linear-gradient(to bottom, black, transparent 85%)",
          }}
        />
        <div className="relative flex flex-wrap items-end justify-between gap-10">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-300 mb-3">
              Total allocated — by currency
            </p>
            {summary.total_allocated_by_currency.length === 0 ? (
              <div className="text-sm text-slate-300">No committed total yet.</div>
            ) : (
              <div className="flex flex-wrap gap-10">
                {summary.total_allocated_by_currency.map((c) => {
                  const count = budgetsPerCurrency.get(c.currency ?? "") ?? 0;
                  return (
                    <div key={c.currency ?? "unknown"}>
                      <div className="text-4xl font-bold tabular-nums">
                        {formatCurrency(c.total_allocated, c.currency)}
                      </div>
                      <div className="text-xs text-slate-300 mt-1">
                        {c.currency ?? "—"} across {count} {count === 1 ? "budget" : "budgets"}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
            <span className="inline-flex items-center gap-1.5 mt-4 text-[11px] font-semibold px-2.5 py-1 rounded-full bg-amber-400/20 text-amber-200">
              Shown per currency — never blended
            </span>
          </div>
          <div className="flex gap-8">
            <div>
              <div className="text-3xl font-bold tabular-nums">{confirmedBudgets.length}</div>
              <div className="text-xs text-slate-300 mt-1">funded budgets</div>
            </div>
            <div>
              <div className="text-3xl font-bold tabular-nums">{visibleGrantees.length}</div>
              <div className="text-xs text-slate-300 mt-1">grantee organisations</div>
            </div>
          </div>
        </div>
      </div>

      {!hasFundedBudgets ? (
        <div className="flex items-center justify-center py-16 bg-white rounded-lg border border-slate-200">
          <div className="text-center">
            <p className="text-xl font-semibold text-slate-900 mb-2">No funded budgets yet</p>
            <p className="text-gray-600">
              Budgets you fund will show up here once they're created.
            </p>
          </div>
        </div>
      ) : (
        <>
          <div className="mb-12">
            <SectionHead
              title="Grantees"
              hint={`${visibleGrantees.length} ${visibleGrantees.length === 1 ? "organisation" : "organisations"} funded`}
            />
            <div className="flex gap-3 overflow-x-auto snap-x snap-mandatory -mx-4 px-4 sm:mx-0 sm:px-0 sm:overflow-visible sm:snap-none sm:grid sm:grid-cols-2 lg:grid-cols-3 sm:gap-4">
              {visibleGrantees.map((grantee, i) => (
                <GranteeCard
                  key={grantee.id ?? grantee.name ?? i}
                  grantee={grantee}
                  colorClass={AVATAR_COLORS[i % AVATAR_COLORS.length]}
                />
              ))}
            </div>
          </div>

          <div>
            <SectionHead
              title="Funded Budgets"
              hint={`${confirmedBudgets.length} confirmed`}
            />

            {confirmedBudgets.length === 0 ? (
              <div className="flex items-center justify-center py-16 bg-white rounded-lg border border-slate-200">
                <div className="text-center">
                  <p className="text-xl font-semibold text-slate-900 mb-2">
                    No confirmed budgets yet
                  </p>
                  <p className="text-gray-600">
                    Budgets show up here once the grantee confirms them.
                  </p>
                </div>
              </div>
            ) : (
              <>
                {/* Desktop / tablet: table */}
                <div className="hidden sm:block ledger-card">
                  <table className="min-w-full divide-y divide-slate-200">
                    <thead className="bg-slate-50">
                      <tr>
                        <th className="px-4 py-2.5 text-left text-micro-label">Budget</th>
                        <th className="px-4 py-2.5 text-left text-micro-label">Grantee</th>
                        <th className="px-4 py-2.5 text-left text-micro-label">Status</th>
                        <th className="px-4 py-2.5 text-right text-micro-label">Total Amount</th>
                        <th className="px-4 py-2.5 text-right text-micro-label">
                          Total in Local
                        </th>
                        <th className="px-4 py-2.5 text-right text-micro-label">Est. Rate</th>
                        <th className="px-4 py-2.5 text-right text-micro-label">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {confirmedBudgets.map((budget) => (
                        <tr key={budget.id} className="hover:bg-slate-50">
                          <td className="px-4 py-2.5 text-left text-sm font-medium text-slate-900">
                            {budget.name}
                          </td>
                          <td className="px-4 py-2.5 text-left text-sm text-slate-600">
                            {budget.owner?.name ?? "—"}
                          </td>
                          <td className="px-4 py-2.5 text-left">
                            <StatusBadge status={budget.status} />
                          </td>
                          <BudgetAmountCells budget={budget} />
                          <td className="px-4 py-2.5 text-right">
                            <div className="flex gap-2 justify-end">
                              <BudgetActions budgetId={budget.id} />
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Mobile: compact list rows instead of a table */}
                <div className="sm:hidden flex flex-col gap-2">
                  {confirmedBudgets.map((budget) => (
                    <div
                      key={budget.id}
                      className="bg-white border border-slate-200 rounded-xl p-3 flex flex-col gap-2"
                    >
                      <div className="flex items-center gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-semibold text-slate-900 truncate">
                              {budget.name}
                            </span>
                            <StatusBadge status={budget.status} />
                          </div>
                          <div className="text-xs text-slate-500 mt-0.5 truncate">
                            {budget.owner?.name ?? "—"}
                          </div>
                        </div>
                        <BudgetAmountInline budget={budget} />
                      </div>
                      <div className="flex gap-2">
                        <BudgetActions budgetId={budget.id} />
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}
