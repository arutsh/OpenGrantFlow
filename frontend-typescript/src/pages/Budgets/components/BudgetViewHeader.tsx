import { useEffect, useState } from "react";
import { Archive, Download, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import Button, { ConfirmDeleteButton } from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import {
  editBudget,
  exportBudgetWorkbook,
  saveBudgetAsTemplate,
} from "@/api/budgetApi";
import { useFunderPicker } from "@/hooks/useFunderPicker";
import {
  getCurrentCustomerId,
  isBudgetFunder,
  isBudgetOwner,
} from "@/utils/roleAccess";
import { formatDateOnly } from "@/utils/datetime";
import { CURRENCY_CODES } from "@/utils/currency";
import { Budget } from "../types/budget";
import { STATUS_LABELS, STATUS_STYLES } from "../constants/budgetStatus";

function ownerTypeLabel(
  owner?: { is_ngo?: boolean; is_donor?: boolean } | null,
): string {
  const tags = [owner?.is_ngo && "NGO", owner?.is_donor && "Donor"].filter(
    Boolean,
  );
  return tags.length ? ` (${tags.join(" / ")})` : "";
}

export function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_STYLES[status] ?? STATUS_STYLES.draft;
  const label = STATUS_LABELS[status] ?? status;
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide px-2.5 py-1 rounded-full mb-2 ${cls}`}
    >
      {status === "archived" ? (
        <Archive className="w-3 h-3" />
      ) : (
        <span className="w-1.5 h-1.5 rounded-full bg-current" />
      )}
      {label}
    </span>
  );
}

export function BudgetViewHeader({
  budget,
  isLocked,
  onBudgetUpdated,
  editTrigger,
}: {
  budget: Budget;
  // Metadata/lines lock as soon as the budget is confirmed — not only once a
  // report exists (a report can only ever be created against an
  // already-confirmed budget, so "confirmed" is the correct, broader gate;
  // there's a real confirmed-but-reportless window the old report-based
  // check would have wrongly left editable).
  isLocked: boolean;
  onBudgetUpdated?: (updated: Budget) => void;
  // Bumped by a sibling section (e.g. CurrencyLedgerPanel's "set actual
  // currency first" prompt) to open edit mode from outside this component,
  // without lifting isEditMode itself into shared state. Only reacts to a
  // change from a defined value, so it never fires on initial mount.
  editTrigger?: number;
}) {
  const [isEditMode, setIsEditMode] = useState(false);
  const [name, setName] = useState(budget.name ?? "");
  const [durationMonths, setDurationMonths] = useState<number | "">(
    budget.duration_months ?? "",
  );
  const [localCurrency, setLocalCurrency] = useState(
    budget.local_currency ?? "",
  );
  const [actualCurrency, setActualCurrency] = useState(
    budget.actual_currency ?? "",
  );
  const [donorTotalAmount, setDonorTotalAmount] = useState<number | "">(
    budget.donor_total_amount ?? "",
  );
  const [estimatedExchangeRate, setEstimatedExchangeRate] = useState<
    number | ""
  >(budget.estimated_exchange_rate ?? "");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  // True when edit mode was entered via editTrigger on an already-locked
  // (confirmed) budget — restricts the form to the actual-currency field
  // only, both visually and in the payload sent on save, since the backend
  // still locks every other metadata field once confirmed.
  const [isCurrencyOnlyEdit, setIsCurrencyOnlyEdit] = useState(false);
  // Shared with BudgetConfirmAction/BudgetCancelConfirmationAction so the
  // Edit button can't be clicked mid-confirm/revert — without this, entering
  // edit mode while one of those requests is in flight lets a stale edit
  // form save metadata against a budget whose status just changed underneath
  // it, failing with a confusing "confirmed" edit-lock error.
  const [isActionBusy, setIsActionBusy] = useState(false);

  // AI-drafted budgets open straight into edit mode so the owner can review
  // the AI-proposed metadata/lines before they're real — same behavior as
  // the previous separate BudgetEditMode screen.
  useEffect(() => {
    if (budget.status === "ai_draft") setIsEditMode(true);
  }, [budget.status]);

  const currentCustomerId = getCurrentCustomerId();
  const owner = isBudgetOwner(budget, currentCustomerId);

  // Grantee's own approved-donor list, for the funder picker below — only
  // fetched while actually editing (not the currency-only form, which never
  // touches funder), same enabled-gating convention as AddBudgetModal.
  const {
    donors,
    isPending: donorsPending,
    isError: donorsError,
    selectedDonorId,
    funderName,
    handleDonorChange,
    handleFunderNameChange,
    reset: resetFunderPicker,
    hasFunder,
  } = useFunderPicker(isEditMode && !isCurrencyOnlyEdit, {
    donorId: budget.funder?.id,
    donorName: budget.funder?.name,
  });

  const enterEdit = () => {
    setName(budget.name ?? "");
    resetFunderPicker({ donorId: budget.funder?.id, donorName: budget.funder?.name });
    setDurationMonths(budget.duration_months ?? "");
    setLocalCurrency(budget.local_currency ?? "");
    setActualCurrency(budget.actual_currency ?? "");
    setDonorTotalAmount(budget.donor_total_amount ?? "");
    setEstimatedExchangeRate(budget.estimated_exchange_rate ?? "");
    setError("");
    setIsCurrencyOnlyEdit(false);
    setIsEditMode(true);
  };

  // Only reachable while isLocked (the normal Edit button is hidden once
  // locked) — restricts the form to actual_currency so the saved payload
  // never carries name/duration/funder, which the backend still blocks on a
  // confirmed budget.
  const enterCurrencyOnlyEdit = () => {
    setActualCurrency(budget.actual_currency ?? "");
    setError("");
    setIsCurrencyOnlyEdit(true);
    setIsEditMode(true);
  };

  useEffect(() => {
    if (editTrigger === undefined) return;
    if (isLocked) enterCurrencyOnlyEdit();
    else enterEdit();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editTrigger]);

  const discardEdit = () => {
    setIsEditMode(false);
    setIsCurrencyOnlyEdit(false);
    setError("");
  };

  // Donor commitment can be zero (no commitment yet), but the estimated
  // rate can't — a zero rate divides by zero everywhere it's used to
  // convert an amount back to the donor's currency (see
  // BudgetViewLinesTable's toDonorAmount).
  const donorAmountInvalid = donorTotalAmount !== "" && Number(donorTotalAmount) < 0;
  const estimatedRateInvalid =
    estimatedExchangeRate !== "" && Number(estimatedExchangeRate) <= 0;

  const saveEdit = async () => {
    setIsSaving(true);
    setError("");
    try {
      const updated = await editBudget(
        budget.id,
        isCurrencyOnlyEdit
          ? { actual_currency: actualCurrency.trim() || undefined }
          : {
              name: name.trim() || undefined,
              // Always sent (even blank) — this form always carries the
              // budget's full current metadata, so an empty value here
              // means the user intentionally cleared it, not "leave
              // unchanged". Cleared to "" whenever a donor is selected,
              // since the two are mutually exclusive.
              external_funder_name: selectedDonorId ? "" : funderName.trim(),
              // Also always sent, as explicit `null` when unset — same
              // "full metadata every save" convention as external_funder_name
              // above, so switching away from a donor-linked funder actually
              // clears funding_customer_id instead of leaving it stale.
              funding_customer_id: selectedDonorId || null,
              duration_months:
                durationMonths !== "" ? Number(durationMonths) : undefined,
              local_currency: localCurrency.trim() || undefined,
              actual_currency: actualCurrency.trim() || undefined,
              // Explicit `null` (not `undefined`) when the user blanks the
              // field — `undefined` is dropped from the JSON body entirely,
              // which the backend reads as "field omitted, leave
              // unchanged", so it could never actually be cleared.
              donor_total_amount:
                donorTotalAmount !== "" ? Number(donorTotalAmount) : null,
              estimated_exchange_rate:
                estimatedExchangeRate !== "" ? Number(estimatedExchangeRate) : null,
              status: budget.status === "ai_draft" ? "draft" : undefined,
            },
      );
      onBudgetUpdated?.(updated);
      setIsEditMode(false);
      setIsCurrencyOnlyEdit(false);
    } catch {
      setError("Failed to save changes. Please try again.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <>
      <Card className="w-full bg-white rounded-xl border border-slate-200 shadow-sm px-6 py-5">
        <CardHeader>
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div className="flex-1 min-w-[240px]">
              <StatusBadge status={budget.status} />
              {isEditMode && !isCurrencyOnlyEdit ? (
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  disabled={isSaving}
                  className="block w-full max-w-md text-2xl font-semibold border border-slate-300 rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-slate-400"
                />
              ) : (
                <h1 className="text-2xl font-semibold">{budget.name}</h1>
              )}
            </div>
            <div className="flex items-center gap-2">
              <BudgetActionsToolbar budget={budget} />
              {isEditMode ? (
                <>
                  <Button
                    variant="secondary"
                    onClick={discardEdit}
                    disabled={isSaving}
                  >
                    Discard
                  </Button>
                  <Button
                    variant="primary"
                    onClick={saveEdit}
                    disabled={
                      isSaving ||
                      (!isCurrencyOnlyEdit &&
                        (!name.trim() ||
                          !hasFunder ||
                          (durationMonths !== "" && durationMonths < 1) ||
                          donorAmountInvalid ||
                          estimatedRateInvalid))
                    }
                  >
                    {isSaving ? "Saving..." : "Save Changes"}
                  </Button>
                </>
              ) : owner && isLocked ? (
                <span
                  className="inline-flex items-center gap-1.5 text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200 px-2.5 py-1.5 rounded-lg"
                  title="This budget is confirmed — its metadata and lines are locked to keep reported figures accurate."
                >
                  🔒 Locked: confirmed
                </span>
              ) : owner ? (
                <Button
                  variant="secondary"
                  onClick={enterEdit}
                  className="text-sm"
                  disabled={isActionBusy}
                >
                  Edit
                </Button>
              ) : null}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isEditMode && !isCurrencyOnlyEdit ? (
            <div className="mt-1 flex items-center flex-wrap gap-2 text-sm text-slate-500">
              <span className="text-slate-700 font-medium">
                {budget.owner?.name ?? "Unknown"}
              </span>
              {ownerTypeLabel(budget.owner)}
              <span className="text-slate-300">→</span>
              {donors.length > 0 && (
                <select
                  aria-label="Donor"
                  value={selectedDonorId}
                  onChange={(e) => handleDonorChange(e.target.value)}
                  disabled={isSaving}
                  className="border border-slate-300 rounded-lg px-2 py-1 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-400"
                >
                  <option value="">— choose an approved donor —</option>
                  {donors.map((donor) => (
                    <option key={donor.id} value={donor.id}>
                      {donor.name}
                    </option>
                  ))}
                </select>
              )}
              {donors.length > 0 && <span className="text-slate-300 text-xs">or</span>}
              <input
                type="text"
                value={funderName}
                onChange={(e) => handleFunderNameChange(e.target.value)}
                disabled={isSaving || !!selectedDonorId}
                placeholder="Custom funder name"
                className="border border-slate-300 rounded-lg px-2 py-1 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-400 disabled:bg-slate-100"
              />
              {donors.length === 0 && donorsError && (
                <span className="text-xs text-red-500">
                  Failed to load your approved donors.
                </span>
              )}
              {donors.length === 0 && !donorsError && !donorsPending && (
                <span className="text-xs text-slate-400">No approved donors yet.</span>
              )}
              {!hasFunder && (
                <span className="text-xs text-red-500">
                  Select a donor or enter a funder name.
                </span>
              )}
            </div>
          ) : (
            <p className="text-sm text-slate-500 mt-1">
              <span className="text-slate-700 font-medium">
                {budget.owner?.name ?? "Unknown"}
              </span>
              {ownerTypeLabel(budget.owner)}
              <span className="mx-1.5 text-slate-300">→</span>
              <span className="text-slate-700 font-medium">
                {budget.funder?.name ?? "—"}
              </span>
            </p>
          )}

          {isCurrencyOnlyEdit && (
            <p className="text-xs text-amber-700 mt-2">
              This budget is confirmed — only the actual currency can be
              updated.
            </p>
          )}

          {error && <p className="text-sm text-red-600 mt-2">{error}</p>}

          <div className="mt-4 flex flex-wrap gap-8 pt-4 border-t border-dashed border-slate-200">
            <div>
              <div className="text-micro-label">Start date</div>
              <div className="text-sm font-semibold text-slate-700 mt-0.5">
                {formatDateOnly(budget.start_date) ?? "—"}
              </div>
            </div>
            <div>
              <div className="text-micro-label">End date</div>
              <div className="text-sm font-semibold text-slate-700 mt-0.5">
                {formatDateOnly(budget.end_date) ?? "—"}
              </div>
            </div>
            <div>
              <div className="text-micro-label">Duration</div>
              {isEditMode && !isCurrencyOnlyEdit ? (
                <input
                  type="number"
                  min={1}
                  value={durationMonths}
                  onChange={(e) =>
                    setDurationMonths(
                      e.target.value ? parseInt(e.target.value) : "",
                    )
                  }
                  disabled={isSaving}
                  className="w-20 mt-0.5 border border-slate-300 rounded-lg px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-slate-400"
                />
              ) : (
                <div className="text-sm font-semibold text-slate-700 mt-0.5">
                  {budget.duration_months
                    ? `${budget.duration_months} months`
                    : "—"}
                </div>
              )}
            </div>
            <div>
              <div className="text-micro-label">Currency</div>
              {isEditMode && !isCurrencyOnlyEdit ? (
                <select
                  value={localCurrency}
                  onChange={(e) => setLocalCurrency(e.target.value)}
                  disabled={isSaving}
                  className="mt-0.5 border border-slate-300 rounded-lg px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-slate-400"
                >
                  {/* Always offer the current value, even if off-list. */}
                  {localCurrency &&
                    !CURRENCY_CODES.includes(localCurrency) && (
                      <option value={localCurrency}>{localCurrency}</option>
                    )}
                  {CURRENCY_CODES.map((code) => (
                    <option key={code} value={code}>
                      {code}
                    </option>
                  ))}
                </select>
              ) : (
                <div className="text-sm font-semibold text-slate-700 mt-0.5">
                  {budget.local_currency ?? "—"}
                </div>
              )}
            </div>
            <div>
              <div className="text-micro-label">Original currency</div>
              {isEditMode ? (
                <select
                  value={actualCurrency}
                  onChange={(e) => setActualCurrency(e.target.value)}
                  disabled={isSaving}
                  className="mt-0.5 border border-slate-300 rounded-lg px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-slate-400"
                >
                  <option value="">—</option>
                  {/* Current value always offered, even if outside the fixed
                    list below, so an existing budget's actual_currency is
                    never silently blanked out just by entering edit mode. */}
                  {actualCurrency &&
                    !CURRENCY_CODES.includes(actualCurrency) && (
                      <option value={actualCurrency}>{actualCurrency}</option>
                    )}
                  {CURRENCY_CODES.map((code) => (
                    <option key={code} value={code}>
                      {code}
                    </option>
                  ))}
                </select>
              ) : (
                <div className="text-sm font-semibold text-slate-700 mt-0.5">
                  {budget.actual_currency ?? "—"}
                </div>
              )}
            </div>
            <div>
              <div className="text-micro-label">Donor commitment</div>
              {isEditMode && !isCurrencyOnlyEdit ? (
                <input
                  type="number"
                  min={0}
                  step="any"
                  value={donorTotalAmount}
                  onChange={(e) =>
                    setDonorTotalAmount(
                      e.target.value ? Number(e.target.value) : "",
                    )
                  }
                  disabled={isSaving}
                  className={`w-28 mt-0.5 border rounded-lg px-2 py-1 text-sm focus:outline-none focus:ring-2 ${
                    donorAmountInvalid
                      ? "border-red-300 focus:ring-red-400"
                      : "border-slate-300 focus:ring-slate-400"
                  }`}
                />
              ) : (
                <div className="text-sm font-semibold text-slate-700 mt-0.5">
                  {budget.donor_total_amount != null
                    ? `${budget.donor_total_amount} ${budget.actual_currency ?? ""}`.trim()
                    : "—"}
                </div>
              )}
              {donorAmountInvalid && (
                <p className="text-xs text-red-600 mt-0.5">Must be zero or greater.</p>
              )}
            </div>
            <div>
              <div className="text-micro-label">Estimated rate</div>
              {isEditMode && !isCurrencyOnlyEdit ? (
                <input
                  type="number"
                  min={0}
                  step="any"
                  value={estimatedExchangeRate}
                  onChange={(e) =>
                    setEstimatedExchangeRate(
                      e.target.value ? Number(e.target.value) : "",
                    )
                  }
                  disabled={isSaving}
                  className={`w-24 mt-0.5 border rounded-lg px-2 py-1 text-sm focus:outline-none focus:ring-2 ${
                    estimatedRateInvalid
                      ? "border-red-300 focus:ring-red-400"
                      : "border-slate-300 focus:ring-slate-400"
                  }`}
                />
              ) : (
                <div className="text-sm font-semibold text-slate-700 mt-0.5">
                  {budget.estimated_exchange_rate ?? "—"}
                </div>
              )}
              {estimatedRateInvalid && (
                <p className="text-xs text-red-600 mt-0.5">Must be greater than zero.</p>
              )}
            </div>
          </div>

          {!isEditMode && (
            <>
              <BudgetConfirmAction
                budget={budget}
                onConfirmed={onBudgetUpdated}
                onBusyChange={setIsActionBusy}
              />
              <BudgetCancelConfirmationAction
                budget={budget}
                onReverted={onBudgetUpdated}
                onBusyChange={setIsActionBusy}
              />
            </>
          )}
        </CardContent>
      </Card>
    </>
  );
}

// Icon-button cluster for lightweight actions — export today, room for more later.
function BudgetActionsToolbar({ budget }: { budget: Budget }) {
  const canExport =
    isBudgetOwner(budget, getCurrentCustomerId()) ||
    isBudgetFunder(budget, getCurrentCustomerId());

  if (!canExport) return null;

  return (
    <div className="flex items-center gap-0.5 bg-slate-50 border border-slate-200 rounded-lg p-0.5">
      <ExportBudgetAction budget={budget} />
    </div>
  );
}

function ExportBudgetAction({ budget }: { budget: Budget }) {
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState("");

  const handleExport = async () => {
    setIsExporting(true);
    setError("");
    try {
      const blob = await exportBudgetWorkbook(budget.id);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${budget.name}.xlsx`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      setError("Failed to export budget. Please try again.");
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="relative">
      <Button
        variant="icon"
        title="Export to Excel"
        onClick={handleExport}
        disabled={isExporting}
      >
        {isExporting ? <Loader2 size={18} className="animate-spin" /> : <Download size={18} />}
      </Button>
      {error && (
        <p className="absolute right-0 top-full mt-1 w-48 text-xs text-red-600 bg-white border border-red-200 rounded-md shadow-md p-2 z-10">
          {error}
        </p>
      )}
    </div>
  );
}

function BudgetConfirmAction({
  budget,
  onConfirmed,
  onBusyChange,
}: {
  budget: Budget;
  onConfirmed?: (updated: Budget) => void;
  onBusyChange?: (busy: boolean) => void;
}) {
  // Seeded from budget.start_date (not blank) so a budget that was already
  // confirmed once — then reverted via Cancel Confirmation, which leaves
  // start_date unchanged — doesn't force the owner to redundantly retype a
  // date the system already has on record.
  const [startDate, setStartDate] = useState(budget.start_date ?? "");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  // Set once a confirm response says this budget is eligible for the
  // optional "save as reusable template" prompt (budget-excel-import spec,
  // group 2) — kept in local state so it survives isConfirmable flipping to
  // false on the very next render once the budget is confirmed.
  const [templatePromptBudgetId, setTemplatePromptBudgetId] = useState<
    string | null
  >(null);

  const currentCustomerId = getCurrentCustomerId();
  const isConfirmable =
    budget.status === "draft" || budget.status === "ai_draft";
  const canConfirm =
    isBudgetOwner(budget, currentCustomerId) ||
    isBudgetFunder(budget, currentCustomerId);

  // Re-sync whenever the widget becomes visible again (e.g. after a revert),
  // covering the case where this component's state outlives the round trip
  // without a remount, not just the initial-mount case above.
  useEffect(() => {
    if (isConfirmable) setStartDate(budget.start_date ?? "");
  }, [isConfirmable, budget.start_date]);

  const handleConfirm = async () => {
    if (!startDate) return;
    setIsSaving(true);
    onBusyChange?.(true);
    setError("");
    try {
      const updated = await editBudget(budget.id, {
        start_date: startDate,
        status: "confirmed",
      });
      onConfirmed?.(updated);
      if (updated.can_save_as_template) {
        setTemplatePromptBudgetId(updated.id);
      }
    } catch {
      setError("Failed to confirm budget. Please try again.");
    } finally {
      setIsSaving(false);
      onBusyChange?.(false);
    }
  };

  // Rendered independent of isConfirmable/canConfirm below — set from this
  // component's own handleConfirm result, not derived from the budget prop,
  // so it doesn't depend on (or race) the parent re-rendering with a fresh
  // budget after the confirm PATCH resolves.
  const templatePrompt = templatePromptBudgetId ? (
    <SaveAsTemplatePrompt
      budgetId={templatePromptBudgetId}
      onDone={() => setTemplatePromptBudgetId(null)}
    />
  ) : null;

  if (!isConfirmable || !canConfirm) {
    return templatePrompt;
  }

  return (
    <>
      <div className="mt-4 pt-3 border-t border-dashed border-slate-200 flex flex-wrap items-center justify-end gap-2">
        <span className="text-xs text-slate-400 mr-auto">
          Confirm to unlock reporting
        </span>
        <label htmlFor="start_date" className="text-xs text-slate-500">
          Start date
        </label>
        <div className="[&>div]:mb-0">
          <Input
            name="start_date"
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            disabled={isSaving}
            showLabel={false}
          />
        </div>
        <Button
          variant="primary"
          onClick={handleConfirm}
          disabled={!startDate || isSaving}
          className="text-sm"
        >
          {isSaving ? "Confirming..." : "Confirm Budget"}
        </Button>
        {error && (
          <p className="text-sm text-red-600 w-full text-right">{error}</p>
        )}
      </div>
      {templatePrompt}
    </>
  );
}

function SaveAsTemplatePrompt({
  budgetId,
  onDone,
}: {
  budgetId: string;
  onDone: () => void;
}) {
  const [name, setName] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  const handleSave = async () => {
    if (!name.trim()) return;
    setIsSaving(true);
    setError("");
    try {
      await saveBudgetAsTemplate(budgetId, name.trim());
      setSaved(true);
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail;
      setError(detail || "Failed to save template. Please try again.");
    } finally {
      setIsSaving(false);
    }
  };

  if (saved) {
    return (
      <div className="mt-4 pt-3 border-t border-dashed border-slate-200 text-sm text-emerald-700">
        Saved as a reusable template — future imports of this donor's layout
        will skip AI extraction.
      </div>
    );
  }

  return (
    <div className="mt-4 pt-3 border-t border-dashed border-slate-200 flex flex-wrap items-center justify-end gap-2">
      <span className="text-xs text-slate-400 mr-auto">
        Save this layout as a reusable template for future imports?
      </span>
      <div className="[&>div]:mb-0">
        <Input
          name="template_name"
          type="text"
          placeholder="Template name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={isSaving}
          showLabel={false}
        />
      </div>
      <Button
        variant="primary"
        onClick={handleSave}
        disabled={!name.trim() || isSaving}
        className="text-sm"
      >
        {isSaving ? "Saving..." : "Save Template"}
      </Button>
      <Button
        variant="secondary"
        onClick={onDone}
        disabled={isSaving}
        className="text-sm"
      >
        Dismiss
      </Button>
      {error && (
        <p className="text-sm text-red-600 w-full text-right">{error}</p>
      )}
    </div>
  );
}

function BudgetCancelConfirmationAction({
  budget,
  onReverted,
  onBusyChange,
}: {
  budget: Budget;
  onReverted?: (updated: Budget) => void;
  onBusyChange?: (busy: boolean) => void;
}) {
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");

  const currentCustomerId = getCurrentCustomerId();
  if (
    budget.status !== "confirmed" ||
    !isBudgetOwner(budget, currentCustomerId)
  )
    return null;

  const handleCancel = async () => {
    setIsSaving(true);
    onBusyChange?.(true);
    setError("");
    try {
      const updated = await editBudget(budget.id, { status: "draft" });
      onReverted?.(updated);
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail;
      setError(detail || "Failed to cancel confirmation. Please try again.");
    } finally {
      setIsSaving(false);
      onBusyChange?.(false);
    }
  };

  return (
    <div className="mt-4 pt-3 border-t border-dashed border-slate-200 flex flex-wrap items-center justify-end gap-2">
      <span className="text-xs text-slate-400 mr-auto">
        This budget is confirmed
      </span>
      <ConfirmDeleteButton
        variant="danger"
        onConfirm={handleCancel}
        disabled={isSaving}
        className="text-sm"
        confirmMessage="This will delete any draft report(s) on this budget — this can't be undone."
      >
        {isSaving ? "Cancelling..." : "Cancel Confirmation"}
      </ConfirmDeleteButton>
      {error && (
        <p className="text-sm text-red-600 w-full text-right">{error}</p>
      )}
    </div>
  );
}
