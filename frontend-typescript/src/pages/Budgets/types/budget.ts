export interface UserOut {
  id?: string;
  first_name?: string;
  last_name?: string;
  email?: string;
}

export interface CustomerOut {
  id?: string;
  name?: string;
  is_ngo?: boolean;
  is_donor?: boolean;
}

export interface TraceEvent {
  user?: UserOut;
  event_date?: string | null; // ISO date string
}

export interface TraceOut {
  created?: TraceEvent;
  updated?: TraceEvent;
}
export interface BudgetCategory {
  id: string;
  name: string;
  code: string;
  budget_id: string;
}

export interface NewBudgetLine {
  budget_id: string;
  description: string;
  amount: number;
  extra_fields?: Record<string, string>;
  category_name?: string;
  category_id?: string;
}

export interface BudgetLine extends NewBudgetLine {
  id: string;
  category?: BudgetCategory;
}

export interface Budget {
  id: string;
  name?: string;
  status: string;
  duration_months?: number;
  local_currency?: string;
  actual_currency?: string;
  start_date?: string | null; // ISO date string
  end_date?: string | null; // ISO date string — computed backend-side from start_date + duration_months
  total_amount?: number;
  // Donor's stated commitment, in actual_currency — directly entered, not derived.
  donor_total_amount?: number | null;
  // Grantee's own planning-time estimate of actual_currency -> local_currency, entered up front.
  estimated_exchange_rate?: number | null;
  // Set when the budget transitions to confirmed; refreshed on revert + re-confirm.
  confirmed_at?: string | null; // ISO date string
  // Read-only, computed backend-side as donor_total_amount * estimated_exchange_rate; null when either input is unset.
  estimated_local_cap?: number | null;
  // Gates the "save as reusable template" prompt on confirm.
  can_save_as_template?: boolean;
  owner?: CustomerOut;
  funder?: CustomerOut | { name?: string; id?: string };
  trace?: TraceOut;
  lines?: BudgetLine[];
}

// Define a separate type for editing (input data)
export interface BudgetUpdate {
  name?: string;
  owner_id?: string;
  // Explicit `null` clears the field on save (switching to a free-text
  // funder); `undefined` (the key omitted entirely) leaves it unchanged —
  // same convention as donor_total_amount/estimated_exchange_rate below,
  // see BudgetViewHeader's saveEdit.
  funding_customer_id?: string | null;
  external_funder_name?: string;
  duration_months?: number;
  status?: string;
  local_currency?: string;
  actual_currency?: string;
  start_date?: string;
  // Explicit `null` clears the field on save; `undefined` (the key omitted
  // entirely) leaves it unchanged — see BudgetViewHeader's saveEdit.
  donor_total_amount?: number | null;
  estimated_exchange_rate?: number | null;
}

export interface BudgetPatched {
  id: string;
  name?: string;
  owner_id?: string;
  funding_customer_id?: string | null;
  external_funder_name?: string;
  status?: string;
  duration_months?: number;
  local_currency?: string;
  actual_currency?: string;
  start_date?: string | null;
  donor_total_amount?: number | null;
  estimated_exchange_rate?: number | null;
  can_save_as_template?: boolean;
}

// Reports

export type ReportStatus = "draft" | "submitted" | "approved" | "rejected";

export interface Report {
  id: string;
  budget_id?: string;
  name?: string;
  status: ReportStatus;
  period_start?: string | null; // ISO date string
  period_end?: string | null;
  submitted_at?: string | null;
  reviewed_at?: string | null;
  reviewed_by?: string | null;
  review_notes?: string | null;
  created_by?: string;
  updated_by?: string;
  updated_at?: string;
  created_at?: string;
}

export interface ReportWithLines extends Report {
  lines: ReportLine[];
}

// Report plus its parent budget's name/status/funder — returned by the
// cross-budget reports directory endpoint (GET /reports/).
export interface ReportWithBudgetInfo extends Report {
  budget_name?: string | null;
  budget_status?: string | null;
  funding_customer_id?: string | null;
  external_funder_name?: string | null;
  owner_id?: string | null;
  owner_name?: string | null;
}

export interface ReportCreate {
  budget_id: string;
  name: string;
  period_start?: string;
  period_end?: string;
}

export interface ReportUpdate {
  name?: string;
  period_start?: string | null;
  period_end?: string | null;
}

export interface ReportReviewRequest {
  decision: ReportStatus;
  review_notes?: string;
}

export interface ReportLine {
  id: string;
  report_id?: string;
  budget_line_id?: string;
  description?: string;
  amount?: number;
  // The real-world date the expense happened — distinct from created_at
  // (when the row was written).
  expense_date?: string; // ISO date string
  extra_fields?: Record<string, unknown> | null;
  created_by?: string;
  updated_by?: string;
  updated_at?: string;
  created_at?: string;
}

export interface ReportLineCreate {
  report_id: string;
  budget_line_id: string;
  description: string;
  amount: number;
  expense_date: string;
  extra_fields?: Record<string, unknown>;
}

export interface ReportLineUpdate {
  report_id: string;
  description?: string;
  amount?: number;
  expense_date?: string;
  extra_fields?: Record<string, unknown>;
}

export interface Attachment {
  id: string;
  report_line_id?: string;
  filename?: string;
  content_type?: string;
  size?: number;
  storage_key?: string;
  created_by?: string;
  updated_by?: string;
  updated_at?: string;
  created_at?: string;
}

// Currency ledger

export interface FundingReceipt {
  id: string;
  budget_id?: string;
  amount?: number;
  received_at?: string; // ISO date string
  created_by?: string;
  updated_by?: string;
  updated_at?: string;
  created_at?: string;
}

export interface FundingReceiptCreate {
  budget_id: string;
  amount: number;
  received_at: string;
}

export interface FundingReceiptUpdate {
  amount?: number;
  received_at?: string;
}

export interface CurrencyConversion {
  id: string;
  budget_id?: string;
  donor_amount?: number;
  local_amount?: number;
  converted_at?: string; // ISO date string
  created_by?: string;
  updated_by?: string;
  updated_at?: string;
  created_at?: string;
}

export interface CurrencyConversionCreate {
  budget_id: string;
  donor_amount: number;
  local_amount: number;
  converted_at: string;
}

// Per-currency balances only — never blended into one figure, per
// design.md's "group by currency, never blend" rule.
export interface LedgerBalance {
  budget_id: string;
  actual_currency: string | null;
  donor_balance: number;
  local_currency: string | null;
  local_balance: number;
}

export interface BudgetLinePreview {
  category_name: string;
  description: string;
  amount: number;
  extra_fields?: Record<string, unknown> | null;
}

export interface CreateBudgetWithLinesRequest {
  budget_name: string;
  external_funder_name: string;
  duration_months?: number | null;
  lines: BudgetLinePreview[];
}

export interface DonorTemplate {
  id: number;
  name: string;
  categories?: BudgetCategory[];
}
