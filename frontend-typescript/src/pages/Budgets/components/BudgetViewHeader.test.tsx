import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { vi, type Mock } from "vitest";
import { BudgetViewHeader } from "./BudgetViewHeader";
import { Budget } from "../types/budget";
import * as budgetApi from "@/api/budgetApi";
import * as roleAccess from "@/utils/roleAccess";
import * as donorGranteeApi from "@/api/donorGranteeApi";
import * as customerApi from "@/api/customerApi";

vi.mock("@/api/budgetApi", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/budgetApi")>();
  return {
    ...actual,
    editBudget: vi.fn(),
    saveBudgetAsTemplate: vi.fn(),
    exportBudgetWorkbook: vi.fn(),
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

// The funder picker (edit mode only) fetches the grantee's approved-donor
// list — stubbed to empty by default so the rest of this file's tests (which
// predate the picker) keep exercising the free-text-only path unaffected.
vi.mock("@/api/donorGranteeApi", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/donorGranteeApi")>();
  return {
    ...actual,
    listDonorGrantees: vi.fn(),
  };
});

vi.mock("@/api/customerApi", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/customerApi")>();
  return {
    ...actual,
    getCustomersByIds: vi.fn(),
  };
});

const editBudgetMock = budgetApi.editBudget as unknown as ReturnType<typeof vi.fn>;
const saveBudgetAsTemplateMock = budgetApi.saveBudgetAsTemplate as unknown as ReturnType<
  typeof vi.fn
>;
const exportBudgetWorkbookMock = budgetApi.exportBudgetWorkbook as unknown as ReturnType<
  typeof vi.fn
>;
const getCurrentCustomerIdMock = roleAccess.getCurrentCustomerId as unknown as ReturnType<
  typeof vi.fn
>;
const isBudgetOwnerMock = roleAccess.isBudgetOwner as unknown as ReturnType<typeof vi.fn>;
const isBudgetFunderMock = roleAccess.isBudgetFunder as unknown as ReturnType<typeof vi.fn>;
const listDonorGranteesMock = donorGranteeApi.listDonorGrantees as unknown as Mock;
const getCustomersByIdsMock = customerApi.getCustomersByIds as unknown as Mock;

// Set once, not inside a beforeEach — vi.clearAllMocks() (used throughout
// this file) clears call history but not a mock's configured implementation,
// so this default survives every describe block's own beforeEach and only
// needs overriding in the tests that actually exercise the picker.
listDonorGranteesMock.mockResolvedValue([]);

function renderHeader(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const result = render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
  return {
    ...result,
    // Re-wraps in the same QueryClientProvider instance — a bare
    // result.rerender(newUi) would replace the whole tree and drop the
    // provider, breaking every test that rerenders with a new editTrigger.
    rerender: (nextUi: React.ReactElement) =>
      result.rerender(<QueryClientProvider client={queryClient}>{nextUi}</QueryClientProvider>),
  };
}

function makeBudget(overrides: Partial<Budget> = {}): Budget {
  return {
    id: "b1",
    name: "Clean Water Phase 1",
    status: "draft",
    owner: { id: "owner-1", name: "Hope Relief NGO" },
    funder: { id: "funder-1", name: "Donor 7" },
    duration_months: 24,
    ...overrides,
  };
}

describe("BudgetViewHeader confirm action", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getCurrentCustomerIdMock.mockReturnValue("owner-1");
    isBudgetOwnerMock.mockReturnValue(true);
    isBudgetFunderMock.mockReturnValue(false);
  });

  it("hides the Confirm Budget action once the budget is already confirmed", () => {
    renderHeader(
      <BudgetViewHeader budget={makeBudget({ status: "confirmed" })} isLocked={false} />,
    );

    expect(
      screen.queryByRole("button", { name: /confirm budget/i }),
    ).not.toBeInTheDocument();
  });

  it("hides the action for a non-owner, non-funder viewer", () => {
    isBudgetOwnerMock.mockReturnValue(false);
    isBudgetFunderMock.mockReturnValue(false);

    renderHeader(<BudgetViewHeader budget={makeBudget()} isLocked={false} />);

    expect(
      screen.queryByRole("button", { name: /confirm budget/i }),
    ).not.toBeInTheDocument();
  });

  it("shows the action to the matching funder even when they are not the owner", () => {
    isBudgetOwnerMock.mockReturnValue(false);
    isBudgetFunderMock.mockReturnValue(true);

    renderHeader(<BudgetViewHeader budget={makeBudget()} isLocked={false} />);

    expect(screen.getByRole("button", { name: /confirm budget/i })).toBeInTheDocument();
  });

  it("disables the Confirm Budget button until a start date is picked", () => {
    renderHeader(<BudgetViewHeader budget={makeBudget()} isLocked={false} />);

    expect(screen.getByRole("button", { name: /confirm budget/i })).toBeDisabled();
  });

  it("prefills the start date from budget.start_date, so re-confirming after a cancel doesn't require retyping it", () => {
    renderHeader(
      <BudgetViewHeader
        budget={makeBudget({ start_date: "2026-08-01" })}
        isLocked={false}
      />,
    );

    expect(screen.getByLabelText(/start date/i)).toHaveValue("2026-08-01");
    expect(screen.getByRole("button", { name: /confirm budget/i })).not.toBeDisabled();
  });

  it("calls editBudget with the start date and confirmed status, and reports the update", async () => {
    const user = userEvent.setup();
    const updated = makeBudget({ status: "confirmed", start_date: "2026-08-01" });
    editBudgetMock.mockResolvedValue(updated);
    const onBudgetUpdated = vi.fn();

    renderHeader(
      <BudgetViewHeader
        budget={makeBudget()}
        isLocked={false}
        onBudgetUpdated={onBudgetUpdated}
      />,
    );

    const dateInput = screen.getByLabelText(/start date/i);
    await user.type(dateInput, "2026-08-01");

    const confirmButton = screen.getByRole("button", { name: /confirm budget/i });
    expect(confirmButton).not.toBeDisabled();
    await user.click(confirmButton);

    await waitFor(() =>
      expect(editBudgetMock).toHaveBeenCalledWith("b1", {
        start_date: "2026-08-01",
        status: "confirmed",
      }),
    );
    await waitFor(() => expect(onBudgetUpdated).toHaveBeenCalledWith(updated));
  });

  it("shows an inline error and leaves the action visible when the backend rejects confirmation", async () => {
    const user = userEvent.setup();
    editBudgetMock.mockRejectedValue(new Error("rejected"));
    const onBudgetUpdated = vi.fn();

    renderHeader(
      <BudgetViewHeader
        budget={makeBudget()}
        isLocked={false}
        onBudgetUpdated={onBudgetUpdated}
      />,
    );

    const dateInput = screen.getByLabelText(/start date/i);
    await user.type(dateInput, "2026-08-01");
    await user.click(screen.getByRole("button", { name: /confirm budget/i }));

    await waitFor(() =>
      expect(screen.getByText(/failed to confirm budget/i)).toBeInTheDocument(),
    );
    expect(onBudgetUpdated).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /confirm budget/i })).toBeInTheDocument();
  });
});

describe("BudgetViewHeader save-as-template prompt", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getCurrentCustomerIdMock.mockReturnValue("owner-1");
    isBudgetOwnerMock.mockReturnValue(true);
    isBudgetFunderMock.mockReturnValue(false);
  });

  async function confirmBudget(canSaveAsTemplate: boolean) {
    const user = userEvent.setup();
    editBudgetMock.mockResolvedValue(
      makeBudget({
        status: "confirmed",
        start_date: "2026-08-01",
        can_save_as_template: canSaveAsTemplate,
      }),
    );

    renderHeader(<BudgetViewHeader budget={makeBudget()} isLocked={false} />);
    await user.type(screen.getByLabelText(/start date/i), "2026-08-01");
    await user.click(screen.getByRole("button", { name: /confirm budget/i }));
    await waitFor(() => expect(editBudgetMock).toHaveBeenCalled());
    return user;
  }

  it("shows the prompt when the confirm response says the budget is eligible", async () => {
    await confirmBudget(true);

    await waitFor(() =>
      expect(
        screen.getByText(/save this layout as a reusable template/i),
      ).toBeInTheDocument(),
    );
  });

  it("does not show the prompt when the confirm response says the budget is not eligible", async () => {
    await confirmBudget(false);

    await waitFor(() => expect(editBudgetMock).toHaveBeenCalled());
    expect(
      screen.queryByText(/save this layout as a reusable template/i),
    ).not.toBeInTheDocument();
  });

  it("saves the template with the entered name and shows a confirmation", async () => {
    const user = await confirmBudget(true);
    saveBudgetAsTemplateMock.mockResolvedValue({ id: 1, name: "Acme Donor" });

    await waitFor(() =>
      expect(screen.getByPlaceholderText("Template name")).toBeInTheDocument(),
    );
    await user.type(screen.getByPlaceholderText("Template name"), "Acme Donor");
    await user.click(screen.getByRole("button", { name: "Save Template" }));

    await waitFor(() =>
      expect(saveBudgetAsTemplateMock).toHaveBeenCalledWith("b1", "Acme Donor"),
    );
    await waitFor(() =>
      expect(screen.getByText(/saved as a reusable template/i)).toBeInTheDocument(),
    );
  });

  it("shows an error and does not dismiss the prompt when saving the template fails", async () => {
    const user = await confirmBudget(true);
    saveBudgetAsTemplateMock.mockRejectedValue({
      response: { data: { detail: "This budget isn't eligible" } },
    });

    await waitFor(() =>
      expect(screen.getByPlaceholderText("Template name")).toBeInTheDocument(),
    );
    await user.type(screen.getByPlaceholderText("Template name"), "Acme Donor");
    await user.click(screen.getByRole("button", { name: "Save Template" }));

    await waitFor(() =>
      expect(screen.getByText("This budget isn't eligible")).toBeInTheDocument(),
    );
    expect(screen.getByPlaceholderText("Template name")).toBeInTheDocument();
  });

  it("dismisses the prompt without saving", async () => {
    const user = await confirmBudget(true);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Dismiss" })).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: "Dismiss" }));

    expect(saveBudgetAsTemplateMock).not.toHaveBeenCalled();
    expect(
      screen.queryByText(/save this layout as a reusable template/i),
    ).not.toBeInTheDocument();
  });
});

describe("BudgetViewHeader status and dates", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getCurrentCustomerIdMock.mockReturnValue("owner-1");
    isBudgetOwnerMock.mockReturnValue(true);
    isBudgetFunderMock.mockReturnValue(false);
  });

  it("shows the status badge and omits dates when start_date is unset", () => {
    renderHeader(<BudgetViewHeader budget={makeBudget({ status: "draft" })} isLocked={false} />);

    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(2); // start + end date
  });

  it("shows start date, backend-computed end date, and status once confirmed", () => {
    renderHeader(
      <BudgetViewHeader
        budget={makeBudget({
          status: "confirmed",
          start_date: "2026-01-15",
          end_date: "2027-01-15",
          duration_months: 12,
        })}
        isLocked={false}
      />,
    );

    expect(screen.getByText("Confirmed")).toBeInTheDocument();
    expect(screen.getByText("15 Jan 2026")).toBeInTheDocument();
    expect(screen.getByText("15 Jan 2027")).toBeInTheDocument();
  });
});

describe("BudgetViewHeader edit lock", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getCurrentCustomerIdMock.mockReturnValue("owner-1");
    isBudgetOwnerMock.mockReturnValue(true);
    isBudgetFunderMock.mockReturnValue(false);
  });

  it("shows the Edit action when the budget is not locked", () => {
    renderHeader(
      <BudgetViewHeader budget={makeBudget({ status: "draft" })} isLocked={false} />,
    );

    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
  });

  it("hides the Edit action once the budget is locked (confirmed)", () => {
    renderHeader(
      <BudgetViewHeader budget={makeBudget({ status: "confirmed" })} isLocked={true} />,
    );

    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.getByText(/locked: confirmed/i)).toBeInTheDocument();
  });
});

describe("BudgetViewHeader currency-only edit via editTrigger", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getCurrentCustomerIdMock.mockReturnValue("owner-1");
    isBudgetOwnerMock.mockReturnValue(true);
    isBudgetFunderMock.mockReturnValue(false);
  });

  it("opens a currency-only form on a locked budget and saves only actual_currency", async () => {
    const user = userEvent.setup();
    const budget = makeBudget({ status: "confirmed", actual_currency: undefined });
    editBudgetMock.mockResolvedValue(makeBudget({ status: "confirmed", actual_currency: "USD" }));
    const onBudgetUpdated = vi.fn();

    const { rerender } = renderHeader(
      <BudgetViewHeader budget={budget} isLocked onBudgetUpdated={onBudgetUpdated} />,
    );
    rerender(
      <BudgetViewHeader
        budget={budget}
        isLocked
        onBudgetUpdated={onBudgetUpdated}
        editTrigger={1}
      />,
    );

    // Name/funder/duration stay read-only text, not inputs — only currency
    // is editable while the budget is locked.
    expect(screen.queryByDisplayValue("Clean Water Phase 1")).not.toBeInTheDocument();
    expect(screen.getByText("Clean Water Phase 1")).toBeInTheDocument();
    expect(screen.getByText(/only the actual currency can be updated/i)).toBeInTheDocument();

    await user.selectOptions(screen.getByRole("combobox"), "USD");
    await user.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() =>
      expect(editBudgetMock).toHaveBeenCalledWith("b1", { actual_currency: "USD" }),
    );
    await waitFor(() => expect(onBudgetUpdated).toHaveBeenCalled());
  });

  it("still opens the full edit form via editTrigger when the budget is not locked", async () => {
    const budget = makeBudget({ status: "draft" });

    const { rerender } = renderHeader(<BudgetViewHeader budget={budget} isLocked={false} />);
    rerender(<BudgetViewHeader budget={budget} isLocked={false} editTrigger={1} />);

    expect(screen.getByDisplayValue("Clean Water Phase 1")).toBeInTheDocument();
  });
});

describe("BudgetViewHeader cancel confirmation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getCurrentCustomerIdMock.mockReturnValue("owner-1");
    isBudgetOwnerMock.mockReturnValue(true);
    isBudgetFunderMock.mockReturnValue(false);
  });

  it("is hidden on a draft budget", () => {
    renderHeader(<BudgetViewHeader budget={makeBudget({ status: "draft" })} isLocked={false} />);

    expect(
      screen.queryByRole("button", { name: /cancel confirmation/i }),
    ).not.toBeInTheDocument();
  });

  it("is hidden from a non-owner (e.g. the matching funder) on a confirmed budget", () => {
    isBudgetOwnerMock.mockReturnValue(false);

    renderHeader(
      <BudgetViewHeader budget={makeBudget({ status: "confirmed" })} isLocked={false} />,
    );

    expect(
      screen.queryByRole("button", { name: /cancel confirmation/i }),
    ).not.toBeInTheDocument();
  });

  it("requires a second click and shows a warning before reverting", async () => {
    const user = userEvent.setup();
    const onBudgetUpdated = vi.fn();

    renderHeader(
      <BudgetViewHeader
        budget={makeBudget({ status: "confirmed" })}
        isLocked={false}
        onBudgetUpdated={onBudgetUpdated}
      />,
    );

    await user.click(screen.getByRole("button", { name: /cancel confirmation/i }));

    expect(
      screen.getByText(/this will delete any draft report\(s\)/i),
    ).toBeInTheDocument();
    expect(editBudgetMock).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Yes" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "No" })).toBeInTheDocument();
  });

  it("does not revert when the warning is dismissed with No", async () => {
    const user = userEvent.setup();
    const onBudgetUpdated = vi.fn();

    renderHeader(
      <BudgetViewHeader
        budget={makeBudget({ status: "confirmed" })}
        isLocked={false}
        onBudgetUpdated={onBudgetUpdated}
      />,
    );

    await user.click(screen.getByRole("button", { name: /cancel confirmation/i }));
    await user.click(screen.getByRole("button", { name: "No" }));

    expect(editBudgetMock).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /cancel confirmation/i })).toBeInTheDocument();
  });

  it("reverts the budget once the warning is confirmed with Yes", async () => {
    const user = userEvent.setup();
    const reverted = makeBudget({ status: "draft" });
    editBudgetMock.mockResolvedValue(reverted);
    const onBudgetUpdated = vi.fn();

    renderHeader(
      <BudgetViewHeader
        budget={makeBudget({ status: "confirmed" })}
        isLocked={false}
        onBudgetUpdated={onBudgetUpdated}
      />,
    );

    await user.click(screen.getByRole("button", { name: /cancel confirmation/i }));
    await user.click(screen.getByRole("button", { name: "Yes" }));

    await waitFor(() =>
      expect(editBudgetMock).toHaveBeenCalledWith("b1", { status: "draft" }),
    );
    await waitFor(() => expect(onBudgetUpdated).toHaveBeenCalledWith(reverted));
  });

  it("shows the backend's rejection message when blocked by a non-draft report", async () => {
    const user = userEvent.setup();
    editBudgetMock.mockRejectedValue({
      response: {
        data: {
          detail:
            "Cannot revert to draft while the budget has a submitted, approved, or rejected report",
        },
      },
    });
    const onBudgetUpdated = vi.fn();

    renderHeader(
      <BudgetViewHeader
        budget={makeBudget({ status: "confirmed" })}
        isLocked={true}
        onBudgetUpdated={onBudgetUpdated}
      />,
    );

    await user.click(screen.getByRole("button", { name: /cancel confirmation/i }));
    await user.click(screen.getByRole("button", { name: "Yes" }));

    await waitFor(() =>
      expect(
        screen.getByText(/cannot revert to draft while the budget has a submitted/i),
      ).toBeInTheDocument(),
    );
    expect(onBudgetUpdated).not.toHaveBeenCalled();
  });
});

describe("BudgetViewHeader metadata edit", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getCurrentCustomerIdMock.mockReturnValue("owner-1");
    isBudgetOwnerMock.mockReturnValue(true);
    isBudgetFunderMock.mockReturnValue(false);
  });

  it("opens ai_draft budgets straight into edit mode", () => {
    renderHeader(
      <BudgetViewHeader budget={makeBudget({ status: "ai_draft" })} isLocked={false} />,
    );

    expect(screen.getByRole("button", { name: /save changes/i })).toBeInTheDocument();
  });

  it("saves name/funder/duration without touching status or start_date", async () => {
    const user = userEvent.setup();
    const updated = makeBudget({ name: "Renamed" });
    editBudgetMock.mockResolvedValue(updated);
    const onBudgetUpdated = vi.fn();

    renderHeader(
      <BudgetViewHeader
        budget={makeBudget()}
        isLocked={false}
        onBudgetUpdated={onBudgetUpdated}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Edit" }));
    const nameInput = screen.getByDisplayValue("Clean Water Phase 1");
    await user.clear(nameInput);
    await user.type(nameInput, "Renamed");
    await user.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() =>
      expect(editBudgetMock).toHaveBeenCalledWith("b1", {
        name: "Renamed",
        // makeBudget()'s default funder is donor-linked ({ id: "funder-1" }),
        // so entering edit mode preselects that donor rather than the
        // free-text field — external_funder_name stays cleared and
        // funding_customer_id carries the (unchanged) donor id.
        external_funder_name: "",
        funding_customer_id: "funder-1",
        duration_months: 24,
        // Sent as explicit null (not omitted) since the budget never had
        // these set — same as the user clearing them — so the backend
        // reads it as "no commitment", not "leave untouched".
        donor_total_amount: null,
        estimated_exchange_rate: null,
      }),
    );
    await waitFor(() => expect(onBudgetUpdated).toHaveBeenCalledWith(updated));
  });

  it("shows editable donor commitment and estimated rate fields and saves them", async () => {
    const user = userEvent.setup();
    const updated = makeBudget({ donor_total_amount: 10000, estimated_exchange_rate: 0.8 });
    editBudgetMock.mockResolvedValue(updated);
    const onBudgetUpdated = vi.fn();

    renderHeader(
      <BudgetViewHeader
        budget={makeBudget({ actual_currency: "EUR" })}
        isLocked={false}
        onBudgetUpdated={onBudgetUpdated}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Edit" }));

    const donorInput = screen.getByText(/donor commitment/i).parentElement!.querySelector(
      "input",
    ) as HTMLInputElement;
    const rateInput = screen.getByText(/estimated rate/i).parentElement!.querySelector(
      "input",
    ) as HTMLInputElement;
    await user.type(donorInput, "10000");
    await user.type(rateInput, "0.8");

    await user.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() =>
      expect(editBudgetMock).toHaveBeenCalledWith(
        "b1",
        expect.objectContaining({ donor_total_amount: 10000, estimated_exchange_rate: 0.8 }),
      ),
    );
    await waitFor(() => expect(onBudgetUpdated).toHaveBeenCalledWith(updated));
  });

  it("sends explicit null when an existing donor commitment/rate is cleared, so the backend actually clears it", async () => {
    const user = userEvent.setup();
    const updated = makeBudget({ donor_total_amount: null, estimated_exchange_rate: null });
    editBudgetMock.mockResolvedValue(updated);

    renderHeader(
      <BudgetViewHeader
        budget={makeBudget({
          actual_currency: "EUR",
          donor_total_amount: 10000,
          estimated_exchange_rate: 0.8,
        })}
        isLocked={false}
        onBudgetUpdated={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Edit" }));

    const donorInput = screen.getByText(/donor commitment/i).parentElement!.querySelector(
      "input",
    ) as HTMLInputElement;
    const rateInput = screen.getByText(/estimated rate/i).parentElement!.querySelector(
      "input",
    ) as HTMLInputElement;
    await user.clear(donorInput);
    await user.clear(rateInput);

    await user.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() =>
      expect(editBudgetMock).toHaveBeenCalledWith(
        "b1",
        expect.objectContaining({ donor_total_amount: null, estimated_exchange_rate: null }),
      ),
    );
  });

  it("disables Save and shows an error when the estimated rate is zero or negative", async () => {
    const user = userEvent.setup();

    renderHeader(
      <BudgetViewHeader
        budget={makeBudget({ actual_currency: "EUR" })}
        isLocked={false}
        onBudgetUpdated={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Edit" }));
    const rateInput = screen.getByText(/estimated rate/i).parentElement!.querySelector(
      "input",
    ) as HTMLInputElement;
    await user.type(rateInput, "0");

    expect(screen.getByText("Must be greater than zero.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save changes/i })).toBeDisabled();
  });

  it("shows donor commitment and estimated rate as read-only text, not inputs, during a currency-only edit", () => {
    const budget = makeBudget({
      status: "confirmed",
      donor_total_amount: 10000,
      estimated_exchange_rate: 0.8,
      actual_currency: "EUR",
    });

    const { rerender } = renderHeader(
      <BudgetViewHeader budget={budget} isLocked onBudgetUpdated={vi.fn()} />,
    );
    rerender(
      <BudgetViewHeader budget={budget} isLocked onBudgetUpdated={vi.fn()} editTrigger={1} />,
    );

    expect(screen.getByText("10000 EUR")).toBeInTheDocument();
    expect(screen.getByText("0.8")).toBeInTheDocument();
  });

  it("shows the budget's local_currency read-only outside edit mode", () => {
    renderHeader(
      <BudgetViewHeader budget={makeBudget({ local_currency: "EUR" })} isLocked={false} />,
    );

    expect(screen.getByText("Currency").nextElementSibling).toHaveTextContent("EUR");
  });

  it("saves an edited local_currency", async () => {
    const user = userEvent.setup();
    const updated = makeBudget({ local_currency: "USD" });
    editBudgetMock.mockResolvedValue(updated);

    renderHeader(
      <BudgetViewHeader
        budget={makeBudget({ local_currency: "EUR" })}
        isLocked={false}
        onBudgetUpdated={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Edit" }));
    const currencySelect = screen.getByText("Currency").nextElementSibling as HTMLSelectElement;
    await user.selectOptions(currencySelect, "USD");
    await user.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() =>
      expect(editBudgetMock).toHaveBeenCalledWith(
        "b1",
        expect.objectContaining({ local_currency: "USD" }),
      ),
    );
  });

  it("shows local currency as read-only text, not a select, during a currency-only edit", () => {
    const budget = makeBudget({ status: "confirmed", local_currency: "EUR" });

    const { rerender } = renderHeader(
      <BudgetViewHeader budget={budget} isLocked onBudgetUpdated={vi.fn()} />,
    );
    rerender(
      <BudgetViewHeader budget={budget} isLocked onBudgetUpdated={vi.fn()} editTrigger={1} />,
    );

    expect(screen.getByText("Currency").nextElementSibling).toHaveTextContent("EUR");
    expect(screen.getByText("Currency").nextElementSibling?.tagName).not.toBe("SELECT");
  });
});

describe("BudgetViewHeader export action", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getCurrentCustomerIdMock.mockReturnValue("owner-1");
    isBudgetOwnerMock.mockReturnValue(true);
    isBudgetFunderMock.mockReturnValue(false);
    window.URL.createObjectURL = vi.fn(() => "blob:mock-url");
    window.URL.revokeObjectURL = vi.fn();
  });

  it("hides the export action for a non-owner, non-funder viewer", () => {
    isBudgetOwnerMock.mockReturnValue(false);
    isBudgetFunderMock.mockReturnValue(false);

    renderHeader(<BudgetViewHeader budget={makeBudget()} isLocked={false} />);

    expect(screen.queryByTitle("Export to Excel")).not.toBeInTheDocument();
  });

  it("shows the export action to the matching funder even when they are not the owner", () => {
    isBudgetOwnerMock.mockReturnValue(false);
    isBudgetFunderMock.mockReturnValue(true);

    renderHeader(<BudgetViewHeader budget={makeBudget()} isLocked={false} />);

    expect(screen.getByTitle("Export to Excel")).toBeInTheDocument();
  });

  it("downloads the workbook using the budget's name as the filename", async () => {
    const user = userEvent.setup();
    const blob = new Blob(["xlsx-bytes"]);
    exportBudgetWorkbookMock.mockResolvedValue(blob);

    renderHeader(<BudgetViewHeader budget={makeBudget()} isLocked={false} />);
    await user.click(screen.getByTitle("Export to Excel"));

    await waitFor(() => expect(exportBudgetWorkbookMock).toHaveBeenCalledWith("b1"));
    expect(window.URL.createObjectURL).toHaveBeenCalledWith(blob);
    expect(window.URL.revokeObjectURL).toHaveBeenCalledWith("blob:mock-url");
  });

  it("shows an inline error and stays on the page when the export request fails", async () => {
    const user = userEvent.setup();
    exportBudgetWorkbookMock.mockRejectedValue(new Error("failed"));

    renderHeader(<BudgetViewHeader budget={makeBudget()} isLocked={false} />);
    await user.click(screen.getByTitle("Export to Excel"));

    await waitFor(() =>
      expect(screen.getByText(/failed to export budget/i)).toBeInTheDocument(),
    );
    expect(screen.getByTitle("Export to Excel")).toBeInTheDocument();
  });
});

describe("BudgetViewHeader funder picker", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getCurrentCustomerIdMock.mockReturnValue("owner-1");
    isBudgetOwnerMock.mockReturnValue(true);
    isBudgetFunderMock.mockReturnValue(false);
    listDonorGranteesMock.mockResolvedValue([]);
  });

  it("does not render a donor select when the grantee has no approved donors and no existing donor-linked funder", async () => {
    // A free-text-only funder (no id) — unlike makeBudget()'s default
    // donor-linked funder, there's no current selection to fall back to, so
    // this exercises the true "zero options" path.
    renderHeader(
      <BudgetViewHeader
        budget={makeBudget({ funder: { name: "External Co" } })}
        isLocked={false}
      />,
    );

    await userEvent.setup().click(screen.getByRole("button", { name: "Edit" }));

    await waitFor(() => expect(listDonorGranteesMock).toHaveBeenCalled());
    // Only the (unrelated) actual-currency select remains — no donor picker.
    expect(screen.queryByRole("combobox", { name: "Donor" })).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText("Custom funder name")).toBeInTheDocument();
  });

  it("still offers the current donor as an option even when they're no longer in the live approved-donor list", async () => {
    // Regression test: the donor picker used to be seeded once from
    // budget.funder.id and never reconciled against the live donors query —
    // if that donor had since revoked the relationship (so the live list
    // came back without them), the <select> would silently show blank while
    // state still held the stale id, and Save would resubmit it.
    listDonorGranteesMock.mockResolvedValue([]);

    renderHeader(<BudgetViewHeader budget={makeBudget()} isLocked={false} />);
    await userEvent.setup().click(screen.getByRole("button", { name: "Edit" }));

    await waitFor(() =>
      expect(screen.getByRole("combobox", { name: "Donor" })).toBeInTheDocument(),
    );
    expect(screen.getByRole("option", { name: "Donor 7" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Donor" })).toHaveValue("funder-1");
  });

  it("preselects the donor option matching a donor-linked funder, with the free-text field cleared and disabled", async () => {
    const user = userEvent.setup();
    listDonorGranteesMock.mockResolvedValue([
      { id: "dg1", donor_id: "funder-1", grantee_id: "owner-1" },
    ]);
    getCustomersByIdsMock.mockResolvedValue([
      { id: "funder-1", name: "Donor 7", country: "GB", is_ngo: false, is_donor: true, currency: "GBP" },
    ]);

    renderHeader(<BudgetViewHeader budget={makeBudget()} isLocked={false} />);
    await user.click(screen.getByRole("button", { name: "Edit" }));

    const select = await screen.findByDisplayValue("Donor 7");
    expect(select.tagName).toBe("SELECT");
    expect(screen.getByPlaceholderText("Custom funder name")).toHaveValue("");
    expect(screen.getByPlaceholderText("Custom funder name")).toBeDisabled();
  });

  it("prefills the free-text field (not the picker) for a free-text-only funder", async () => {
    const user = userEvent.setup();
    listDonorGranteesMock.mockResolvedValue([
      { id: "dg1", donor_id: "d2", grantee_id: "owner-1" },
    ]);
    getCustomersByIdsMock.mockResolvedValue([
      { id: "d2", name: "Other Donor", country: "GB", is_ngo: false, is_donor: true, currency: "GBP" },
    ]);

    renderHeader(
      <BudgetViewHeader
        budget={makeBudget({ funder: { name: "External Co" } })}
        isLocked={false}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Edit" }));

    await waitFor(() =>
      expect(screen.getByRole("combobox", { name: "Donor" })).toBeInTheDocument(),
    );
    expect(screen.getByPlaceholderText("Custom funder name")).toHaveValue("External Co");
    expect(screen.getByRole("combobox", { name: "Donor" })).toHaveValue("");
  });

  it("switching from a donor-linked funder to a custom name sends explicit null for funding_customer_id", async () => {
    const user = userEvent.setup();
    const updated = makeBudget({ funder: { name: "New Custom Funder" } });
    editBudgetMock.mockResolvedValue(updated);
    listDonorGranteesMock.mockResolvedValue([
      { id: "dg1", donor_id: "funder-1", grantee_id: "owner-1" },
    ]);
    getCustomersByIdsMock.mockResolvedValue([
      { id: "funder-1", name: "Donor 7", country: "GB", is_ngo: false, is_donor: true, currency: "GBP" },
    ]);

    renderHeader(
      <BudgetViewHeader budget={makeBudget()} isLocked={false} onBudgetUpdated={vi.fn()} />,
    );
    await user.click(screen.getByRole("button", { name: "Edit" }));
    await screen.findByDisplayValue("Donor 7");

    // Free text starts disabled (a donor is selected) — clear the donor
    // first, the only path a real user can take to switch.
    await user.selectOptions(screen.getByRole("combobox", { name: "Donor" }), "");
    await user.type(screen.getByPlaceholderText("Custom funder name"), "New Custom Funder");
    await user.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() =>
      expect(editBudgetMock).toHaveBeenCalledWith(
        "b1",
        expect.objectContaining({
          external_funder_name: "New Custom Funder",
          funding_customer_id: null,
        }),
      ),
    );
  });

  it("switching from a free-text funder to a donor sends the donor id and clears external_funder_name", async () => {
    const user = userEvent.setup();
    const updated = makeBudget({ funder: { id: "d2", name: "Other Donor" } });
    editBudgetMock.mockResolvedValue(updated);
    listDonorGranteesMock.mockResolvedValue([
      { id: "dg1", donor_id: "d2", grantee_id: "owner-1" },
    ]);
    getCustomersByIdsMock.mockResolvedValue([
      { id: "d2", name: "Other Donor", country: "GB", is_ngo: false, is_donor: true, currency: "GBP" },
    ]);

    renderHeader(
      <BudgetViewHeader
        budget={makeBudget({ funder: { name: "External Co" } })}
        isLocked={false}
        onBudgetUpdated={vi.fn()}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Edit" }));
    await waitFor(() =>
      expect(screen.getByRole("combobox", { name: "Donor" })).toBeInTheDocument(),
    );
    expect(screen.getByPlaceholderText("Custom funder name")).toHaveValue("External Co");

    await user.selectOptions(screen.getByRole("combobox", { name: "Donor" }), "d2");

    // Mutual exclusivity: selecting a donor clears the free-text value.
    expect(screen.getByPlaceholderText("Custom funder name")).toHaveValue("");
    expect(screen.getByPlaceholderText("Custom funder name")).toBeDisabled();

    await user.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() =>
      expect(editBudgetMock).toHaveBeenCalledWith(
        "b1",
        expect.objectContaining({
          external_funder_name: "",
          funding_customer_id: "d2",
        }),
      ),
    );
  });
});
