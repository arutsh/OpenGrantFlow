import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { vi, type Mock } from "vitest";
import { CurrencyLedgerPanel } from "./CurrencyLedgerPanel";
import { Budget, FundingReceipt, CurrencyConversion, LedgerBalance } from "../types/budget";
import * as currencyLedgerApi from "@/api/currencyLedgerApi";
import * as roleAccess from "@/utils/roleAccess";

vi.mock("@/api/currencyLedgerApi", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/currencyLedgerApi")>();
  return {
    ...actual,
    createFundingReceipt: vi.fn(),
    updateFundingReceipt: vi.fn(),
    deleteFundingReceipt: vi.fn(),
    listFundingReceiptsByBudget: vi.fn(),
    createCurrencyConversion: vi.fn(),
    listCurrencyConversionsByBudget: vi.fn(),
    getLedgerBalance: vi.fn(),
  };
});

vi.mock("@/utils/roleAccess", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/utils/roleAccess")>();
  return {
    ...actual,
    getCurrentCustomerId: vi.fn(),
    isBudgetOwner: vi.fn(),
    isBudgetFunder: vi.fn(),
  };
});

const createFundingReceiptMock = currencyLedgerApi.createFundingReceipt as unknown as Mock;
const updateFundingReceiptMock = currencyLedgerApi.updateFundingReceipt as unknown as Mock;
const deleteFundingReceiptMock = currencyLedgerApi.deleteFundingReceipt as unknown as Mock;
const listFundingReceiptsByBudgetMock =
  currencyLedgerApi.listFundingReceiptsByBudget as unknown as Mock;
const createCurrencyConversionMock =
  currencyLedgerApi.createCurrencyConversion as unknown as Mock;
const listCurrencyConversionsByBudgetMock =
  currencyLedgerApi.listCurrencyConversionsByBudget as unknown as Mock;
const getLedgerBalanceMock = currencyLedgerApi.getLedgerBalance as unknown as Mock;
const getCurrentCustomerIdMock = roleAccess.getCurrentCustomerId as unknown as Mock;
const isBudgetOwnerMock = roleAccess.isBudgetOwner as unknown as Mock;
const isBudgetFunderMock = roleAccess.isBudgetFunder as unknown as Mock;

function makeBudget(overrides: Partial<Budget> = {}): Budget {
  return {
    id: "b1",
    name: "Clean Water Phase 1",
    status: "confirmed",
    owner: { id: "owner-1", name: "Hope Relief NGO" },
    local_currency: "GBP",
    actual_currency: "GBP",
    total_amount: 100000,
    ...overrides,
  };
}

function makeBalance(overrides: Partial<LedgerBalance> = {}): LedgerBalance {
  return {
    budget_id: "b1",
    actual_currency: "GBP",
    donor_balance: 12000,
    local_currency: "GBP",
    local_balance: 3400,
    ...overrides,
  };
}

function renderPanel(budget: Budget, onRequestEditActualCurrency = vi.fn()) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <CurrencyLedgerPanel budget={budget} onRequestEditActualCurrency={onRequestEditActualCurrency} />
    </QueryClientProvider>,
  );
}

describe("CurrencyLedgerPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getCurrentCustomerIdMock.mockReturnValue("owner-1");
    isBudgetOwnerMock.mockReturnValue(true);
    isBudgetFunderMock.mockReturnValue(false);
    listFundingReceiptsByBudgetMock.mockResolvedValue([]);
    listCurrencyConversionsByBudgetMock.mockResolvedValue([]);
    getLedgerBalanceMock.mockResolvedValue(makeBalance());
  });

  it("is hidden for a viewer who is neither owner nor funder", async () => {
    isBudgetOwnerMock.mockReturnValue(false);
    isBudgetFunderMock.mockReturnValue(false);
    renderPanel(makeBudget());

    expect(screen.queryByText("Currency Ledger")).not.toBeInTheDocument();
  });

  it("is visible read-only for a funder — no record buttons, but data loads", async () => {
    isBudgetOwnerMock.mockReturnValue(false);
    isBudgetFunderMock.mockReturnValue(true);
    renderPanel(makeBudget());

    await waitFor(() => expect(screen.getByText("Currency Ledger")).toBeInTheDocument());
    expect(
      screen.queryByRole("button", { name: "+ Record Payment Received" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "+ Record Conversion" }),
    ).not.toBeInTheDocument();
  });

  it("does not show a Set Actual Currency button to a funder when unset", async () => {
    isBudgetOwnerMock.mockReturnValue(false);
    isBudgetFunderMock.mockReturnValue(true);
    renderPanel(makeBudget({ actual_currency: undefined }));

    await waitFor(() => expect(screen.getByText("Currency Ledger")).toBeInTheDocument());
    expect(
      screen.queryByRole("button", { name: "Set Actual Currency" }),
    ).not.toBeInTheDocument();
  });

  it("is hidden when the budget is not confirmed", async () => {
    renderPanel(makeBudget({ status: "draft" }));

    expect(screen.queryByText("Currency Ledger")).not.toBeInTheDocument();
    expect(listFundingReceiptsByBudgetMock).not.toHaveBeenCalled();
  });

  it("shows a set-actual-currency prompt when unset, and calls the edit callback", async () => {
    const onRequestEditActualCurrency = vi.fn();
    renderPanel(makeBudget({ actual_currency: undefined }), onRequestEditActualCurrency);

    await waitFor(() => expect(screen.getByText("Currency Ledger")).toBeInTheDocument());
    expect(
      screen.getByText(/set this budget's actual \(donor-transfer\) currency/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "+ Record Payment Received" }),
    ).not.toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Set Actual Currency" }));
    expect(onRequestEditActualCurrency).toHaveBeenCalled();
  });

  it("shows the record-payment/record-conversion buttons once actual_currency is set, forms hidden until opened", async () => {
    renderPanel(makeBudget());

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "+ Record Payment Received" }),
      ).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: "+ Record Conversion" })).toBeInTheDocument();
    expect(screen.queryByLabelText(/^amount/i)).not.toBeInTheDocument();
  });

  it("shows the balance figures from getLedgerBalance, including a negative local balance as-is", async () => {
    getLedgerBalanceMock.mockResolvedValue(makeBalance({ local_balance: -450 }));
    renderPanel(makeBudget());

    await waitFor(() => expect(screen.getByText(/ready to spend/i)).toBeInTheDocument());
    expect(screen.getByText(/awaiting conversion/i)).toBeInTheDocument();
    expect(screen.getByText("£12,000")).toBeInTheDocument();
    expect(screen.getByText("-£450")).toBeInTheDocument();
  });

  it("shows a received-to-date percentage against the donor commitment", async () => {
    listFundingReceiptsByBudgetMock.mockResolvedValue([
      { id: "r1", budget_id: "b1", amount: 20000, received_at: "2026-06-01" },
      { id: "r2", budget_id: "b1", amount: 20000, received_at: "2026-07-01" },
    ] as FundingReceipt[]);
    renderPanel(
      makeBudget({ local_currency: "GBP", actual_currency: "GBP", donor_total_amount: 100000 }),
    );

    await waitFor(() => expect(screen.getByText("£40,000")).toBeInTheDocument());
    expect(screen.getByText(/40% of £100,000 committed/)).toBeInTheDocument();
  });

  it("shows the percentage against the donor commitment even when currencies differ", async () => {
    listFundingReceiptsByBudgetMock.mockResolvedValue([
      { id: "r1", budget_id: "b1", amount: 20000, received_at: "2026-06-01" },
    ] as FundingReceipt[]);
    renderPanel(
      makeBudget({ local_currency: "KES", actual_currency: "GBP", donor_total_amount: 50000 }),
    );

    await waitFor(() => expect(screen.getByText(/40% of £50,000 committed/)).toBeInTheDocument());
  });

  it("floors the received percentage at 0% when a correction receipt makes the total negative", async () => {
    listFundingReceiptsByBudgetMock.mockResolvedValue([
      { id: "r1", budget_id: "b1", amount: -5000, received_at: "2026-06-01" },
    ] as FundingReceipt[]);
    renderPanel(
      makeBudget({ local_currency: "GBP", actual_currency: "GBP", donor_total_amount: 100000 }),
    );

    await waitFor(() => expect(screen.getByText(/0% of £100,000 committed/)).toBeInTheDocument());
    expect(screen.queryByText(/-5%/)).not.toBeInTheDocument();
  });

  it("shows no percentage or committed figure when the donor commitment isn't set", async () => {
    listFundingReceiptsByBudgetMock.mockResolvedValue([
      { id: "r1", budget_id: "b1", amount: 20000, received_at: "2026-06-01" },
    ] as FundingReceipt[]);
    renderPanel(makeBudget({ donor_total_amount: null }));

    await waitFor(() => expect(screen.getByText("Funding receipt")).toBeInTheDocument());
    expect(screen.queryByText(/% of/)).not.toBeInTheDocument();
    expect(screen.queryByText("Budget Total")).not.toBeInTheDocument();
  });

  it("records a funding receipt with the entered amount and date, and closes the modal", async () => {
    const user = userEvent.setup();
    createFundingReceiptMock.mockResolvedValue({ id: "new-r" });
    renderPanel(makeBudget());

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "+ Record Payment Received" }),
      ).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: "+ Record Payment Received" }));
    expect(screen.getByRole("heading", { name: "Record Payment Received" })).toBeInTheDocument();

    await user.type(screen.getByLabelText(/^amount/i), "5000");
    await user.type(screen.getByLabelText(/received date/i), "2026-06-01");
    await user.click(screen.getByRole("button", { name: "Record Receipt" }));

    await waitFor(() =>
      expect(createFundingReceiptMock).toHaveBeenCalledWith({
        budget_id: "b1",
        amount: 5000,
        received_at: "2026-06-01",
      }),
    );
    await waitFor(() =>
      expect(
        screen.queryByRole("heading", { name: "Record Payment Received" }),
      ).not.toBeInTheDocument(),
    );
  });

  it("records a currency conversion with the entered amounts and date, and closes the modal", async () => {
    const user = userEvent.setup();
    createCurrencyConversionMock.mockResolvedValue({ id: "new-c" });
    renderPanel(makeBudget());

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "+ Record Conversion" })).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: "+ Record Conversion" }));
    expect(screen.getByRole("heading", { name: "Record Currency Conversion" })).toBeInTheDocument();

    await user.type(screen.getByLabelText(/donor amount/i), "3000");
    await user.type(screen.getByLabelText(/local amount/i), "3750");
    await user.type(screen.getByLabelText(/conversion date/i), "2026-06-03");
    await user.click(screen.getByRole("button", { name: "Record Conversion" }));

    await waitFor(() =>
      expect(createCurrencyConversionMock).toHaveBeenCalledWith({
        budget_id: "b1",
        donor_amount: 3000,
        local_amount: 3750,
        converted_at: "2026-06-03",
      }),
    );
    await waitFor(() =>
      expect(
        screen.queryByRole("heading", { name: "Record Currency Conversion" }),
      ).not.toBeInTheDocument(),
    );
  });

  it("lists receipts and conversions chronologically with each conversion's implied rate", async () => {
    listFundingReceiptsByBudgetMock.mockResolvedValue([
      { id: "r1", budget_id: "b1", amount: 20000, received_at: "2026-06-01" },
    ] as FundingReceipt[]);
    listCurrencyConversionsByBudgetMock.mockResolvedValue([
      {
        id: "c1",
        budget_id: "b1",
        donor_amount: 3000,
        local_amount: 3750,
        converted_at: "2026-06-03",
      },
    ] as CurrencyConversion[]);
    renderPanel(makeBudget());

    await waitFor(() => expect(screen.getByText("Funding receipt")).toBeInTheDocument());
    expect(screen.getByText("Conversion")).toBeInTheDocument();
    expect(screen.getByText(/rate 0.8000/)).toBeInTheDocument();
  });

  it("shows an empty history state when there are no receipts or conversions", async () => {
    renderPanel(makeBudget());

    await waitFor(() =>
      expect(
        screen.getByText("No funding receipts or conversions recorded yet."),
      ).toBeInTheDocument(),
    );
  });

  describe("funding receipt edit/delete", () => {
    const receipt = {
      id: "r1",
      budget_id: "b1",
      amount: 20000,
      received_at: "2026-06-01",
    } as FundingReceipt;

    beforeEach(() => {
      listFundingReceiptsByBudgetMock.mockResolvedValue([receipt]);
    });

    it("hides receipt Edit/Delete actions from the funder", async () => {
      isBudgetOwnerMock.mockReturnValue(false);
      isBudgetFunderMock.mockReturnValue(true);
      renderPanel(makeBudget());

      await waitFor(() => expect(screen.getByText("Funding receipt")).toBeInTheDocument());
      expect(screen.queryByTitle("Edit funding receipt")).not.toBeInTheDocument();
      expect(screen.queryByTitle("Delete funding receipt")).not.toBeInTheDocument();
    });

    it("edits a receipt from a prefilled modal and refetches the ledger", async () => {
      const user = userEvent.setup();
      updateFundingReceiptMock.mockResolvedValue({ ...receipt, amount: 25000 });
      renderPanel(makeBudget());

      await waitFor(() => expect(screen.getByTitle("Edit funding receipt")).toBeInTheDocument());
      await user.click(screen.getByTitle("Edit funding receipt"));
      expect(screen.getByRole("heading", { name: "Edit Payment Received" })).toBeInTheDocument();
      expect(screen.getByLabelText(/^amount/i)).toHaveValue(20000);
      expect(screen.getByLabelText(/received date/i)).toHaveValue("2026-06-01");

      await user.clear(screen.getByLabelText(/^amount/i));
      await user.type(screen.getByLabelText(/^amount/i), "25000");
      await user.click(screen.getByRole("button", { name: "Save Changes" }));

      await waitFor(() =>
        expect(updateFundingReceiptMock).toHaveBeenCalledWith("r1", {
          amount: 25000,
          received_at: "2026-06-01",
        }),
      );
      await waitFor(() =>
        expect(
          screen.queryByRole("heading", { name: "Edit Payment Received" }),
        ).not.toBeInTheDocument(),
      );
      expect(listFundingReceiptsByBudgetMock).toHaveBeenCalledTimes(2);
      expect(getLedgerBalanceMock).toHaveBeenCalledTimes(2);
    });

    it("keeps the edit modal open and shows the backend error when an update fails", async () => {
      const user = userEvent.setup();
      updateFundingReceiptMock.mockRejectedValue({
        response: { data: { detail: "Funding Receipt Not found" } },
      });
      renderPanel(makeBudget());

      await waitFor(() => expect(screen.getByTitle("Edit funding receipt")).toBeInTheDocument());
      await user.click(screen.getByTitle("Edit funding receipt"));
      await user.click(screen.getByRole("button", { name: "Save Changes" }));

      await waitFor(() =>
        expect(screen.getByText("Funding Receipt Not found")).toBeInTheDocument(),
      );
      expect(screen.getByRole("heading", { name: "Edit Payment Received" })).toBeInTheDocument();
    });

    it("deletes a receipt after confirmation and refetches the ledger", async () => {
      const user = userEvent.setup();
      deleteFundingReceiptMock.mockResolvedValue(undefined);
      renderPanel(makeBudget());

      await waitFor(() =>
        expect(screen.getByTitle("Delete funding receipt")).toBeInTheDocument(),
      );
      listFundingReceiptsByBudgetMock.mockResolvedValue([]);
      await user.click(screen.getByTitle("Delete funding receipt"));
      expect(deleteFundingReceiptMock).not.toHaveBeenCalled();
      await user.click(screen.getByRole("button", { name: "Yes" }));

      await waitFor(() => expect(deleteFundingReceiptMock).toHaveBeenCalledWith("r1"));
      await waitFor(() =>
        expect(
          screen.getByText("No funding receipts or conversions recorded yet."),
        ).toBeInTheDocument(),
      );
      expect(getLedgerBalanceMock).toHaveBeenCalledTimes(2);
    });

    it("keeps the receipt and shows the backend error when a delete fails", async () => {
      const user = userEvent.setup();
      deleteFundingReceiptMock.mockRejectedValue({
        response: { data: { detail: "Permission denied" } },
      });
      renderPanel(makeBudget());

      await waitFor(() =>
        expect(screen.getByTitle("Delete funding receipt")).toBeInTheDocument(),
      );
      await user.click(screen.getByTitle("Delete funding receipt"));
      await user.click(screen.getByRole("button", { name: "Yes" }));

      await waitFor(() => expect(screen.getByText("Permission denied")).toBeInTheDocument());
      expect(screen.getByText("Funding receipt")).toBeInTheDocument();
    });
  });
});
