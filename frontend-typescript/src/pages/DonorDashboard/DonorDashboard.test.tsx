import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { vi } from "vitest";
import DonorDashboard from "./DonorDashboard";
import * as donorDashboardApi from "@/api/donorDashboardApi";

vi.mock("@/api/donorDashboardApi", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/donorDashboardApi")>();
  return {
    ...actual,
    getFundedBudgetsSummary: vi.fn(),
    getFundedGrantees: vi.fn(),
    getFundedBudgets: vi.fn(),
  };
});

const getFundedBudgetsSummaryMock = donorDashboardApi.getFundedBudgetsSummary as unknown as ReturnType<
  typeof vi.fn
>;
const getFundedGranteesMock = donorDashboardApi.getFundedGrantees as unknown as ReturnType<
  typeof vi.fn
>;
const getFundedBudgetsMock = donorDashboardApi.getFundedBudgets as unknown as ReturnType<
  typeof vi.fn
>;

function renderDashboard() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <DonorDashboard />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("DonorDashboard", () => {
  it("renders the portfolio summary, grantee cards, and funded-budgets table with real-shaped data", async () => {
    getFundedBudgetsSummaryMock.mockResolvedValue({
      total_budgets: 3,
      total_allocated_by_currency: [{ currency: "EUR", total_allocated: 2700 }],
    });
    getFundedGranteesMock.mockResolvedValue([
      {
        id: "g1",
        name: "Hope Relief NGO",
        country: "GB",
        budgets_count: 2,
        total_allocated_by_currency: [{ currency: "EUR", total_allocated: 2000 }],
      },
      {
        id: "g2",
        name: "Clean Water Trust",
        country: "GB",
        budgets_count: 1,
        total_allocated_by_currency: [{ currency: "EUR", total_allocated: 700 }],
      },
    ]);
    getFundedBudgetsMock.mockResolvedValue([
      {
        id: "b1",
        name: "Clean Water Phase 1",
        status: "confirmed",
        total_amount: 1000,
        local_currency: "GBP",
        actual_currency: "EUR",
        estimated_exchange_rate: 0.5,
        owner: { id: "g1", name: "Hope Relief NGO" },
      },
      {
        id: "b2",
        name: "School Rebuild",
        status: "confirmed",
        total_amount: 700,
        local_currency: "GBP",
        actual_currency: "EUR",
        estimated_exchange_rate: 1,
        owner: { id: "g2", name: "Clean Water Trust" },
      },
    ]);

    renderDashboard();

    await waitFor(() => expect(screen.getByText("€2,700")).toBeInTheDocument());

    // Portfolio summary figures — the hero total is in the donor's own
    // currency (EUR), not either grantee's local operating currency (GBP).
    expect(screen.getByText("EUR across 2 budgets")).toBeInTheDocument();
    // Counts follow confirmed budgets only (2 here), not the summary's
    // all-status total_budgets (3), and only grantees with a confirmed budget.
    expect(screen.getByText("funded budgets").previousElementSibling).toHaveTextContent("2");
    expect(screen.getByText("grantee organisations").previousElementSibling).toHaveTextContent(
      "2",
    );

    // Grantee cards — proves both name occurrences (card + budgets-table
    // owner column) render fine, and the card total is in donor currency too.
    expect(screen.getAllByText("Hope Relief NGO").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Clean Water Trust").length).toBeGreaterThan(0);
    expect(screen.getAllByText("€2,000").length).toBeGreaterThan(0);

    // Funded-budgets rows (rendered twice: desktop table + mobile cards) —
    // Total Amount (donor currency, converted via the rate), Total in Local,
    // and Est. Rate all present.
    expect(screen.getAllByText("Clean Water Phase 1").length).toBeGreaterThan(0);
    expect(screen.getAllByText("School Rebuild").length).toBeGreaterThan(0);
    expect(screen.getAllByText("£1,000").length).toBeGreaterThan(0); // b1 local total
    expect(screen.getAllByText("£700").length).toBeGreaterThan(0); // b2 local total
    expect(screen.getAllByText("0.5").length).toBeGreaterThan(0); // b1 rate

    const reportLinks = screen.getAllByRole("link", { name: "View Reports" });
    expect(reportLinks.length).toBeGreaterThan(0);
    reportLinks.forEach((link) => {
      expect(link).toHaveAttribute("href", expect.stringMatching(/^\/budgets\/b[12]\/reports$/));
    });

    const viewBudgetLinks = screen.getAllByRole("link", { name: "View Budget" });
    expect(viewBudgetLinks.length).toBeGreaterThan(0);
    viewBudgetLinks.forEach((link) => {
      expect(link).toHaveAttribute("href", expect.stringMatching(/^\/budgets\/b[12]$/));
    });
  });

  it("renders each currency's total separately in the hero, instead of blending them", async () => {
    getFundedBudgetsSummaryMock.mockResolvedValue({
      total_budgets: 2,
      total_allocated_by_currency: [
        { currency: "GBP", total_allocated: 3000 },
        { currency: "USD", total_allocated: 5000 },
      ],
    });
    getFundedGranteesMock.mockResolvedValue([
      {
        id: "g1",
        name: "Multi-Currency NGO",
        country: "GB",
        budgets_count: 2,
        total_allocated_by_currency: [
          { currency: "GBP", total_allocated: 3000 },
          { currency: "USD", total_allocated: 5000 },
        ],
      },
    ]);
    getFundedBudgetsMock.mockResolvedValue([
      {
        id: "b1",
        name: "GBP Budget",
        status: "confirmed",
        total_amount: 2500,
        local_currency: "GBP",
        owner: { id: "g1", name: "Multi-Currency NGO" },
      },
    ]);

    renderDashboard();

    // Hero shows both currencies as their own separate figures, not joined.
    await waitFor(() => expect(screen.getByText("£3,000")).toBeInTheDocument());
    expect(screen.getByText("US$5,000")).toBeInTheDocument();

    // The grantee card's compact total still joins them (existing convention).
    expect(screen.getByText("£3,000 · US$5,000")).toBeInTheDocument();
  });

  it("shows Total Amount (donor currency), Total in Local, and Est. Rate for a budget with a usable rate", async () => {
    getFundedBudgetsSummaryMock.mockResolvedValue({
      total_budgets: 1,
      total_allocated_by_currency: [{ currency: "EUR", total_allocated: 7500 }],
    });
    getFundedGranteesMock.mockResolvedValue([]);
    getFundedBudgetsMock.mockResolvedValue([
      {
        id: "b1",
        name: "Clean Water Phase 1",
        status: "confirmed",
        total_amount: 6000,
        local_currency: "GBP",
        actual_currency: "EUR",
        estimated_exchange_rate: 0.8,
        donor_total_amount: 10000,
        estimated_local_cap: 8000,
        owner: { id: "g1", name: "Hope Relief NGO" },
      },
    ]);

    renderDashboard();

    await waitFor(() =>
      expect(screen.getAllByText("Clean Water Phase 1").length).toBeGreaterThan(0),
    );
    // Total Amount: 6000 / 0.8 = 7500 EUR (converted real total, not the
    // 10000 EUR donor_total_amount promise).
    expect(screen.getAllByText("€7,500").length).toBeGreaterThan(0);
    // Total in Local: the real local total.
    expect(screen.getAllByText("£6,000").length).toBeGreaterThan(0);
    // Est. Rate.
    expect(screen.getAllByText("0.8").length).toBeGreaterThan(0);
  });

  it("shows — for Total Amount and Est. Rate when a budget has no usable exchange rate", async () => {
    getFundedBudgetsSummaryMock.mockResolvedValue({
      total_budgets: 1,
      total_allocated_by_currency: [],
    });
    getFundedGranteesMock.mockResolvedValue([]);
    getFundedBudgetsMock.mockResolvedValue([
      {
        id: "b1",
        name: "Clean Water Phase 1",
        status: "confirmed",
        total_amount: 1000,
        local_currency: "GBP",
        owner: { id: "g1", name: "Hope Relief NGO" },
      },
    ]);

    renderDashboard();

    await waitFor(() => expect(screen.getAllByText("£1,000").length).toBeGreaterThan(0));
    // Total Amount and Est. Rate both fall back to "—" (desktop table +
    // mobile card, so two of each).
    expect(screen.getAllByText("—").length).toBe(4);
  });

  it("only shows confirmed budgets in the Funded Budgets table, draft budgets excluded", async () => {
    getFundedBudgetsSummaryMock.mockResolvedValue({
      total_budgets: 2,
      total_allocated_by_currency: [{ currency: "EUR", total_allocated: 1000 }],
    });
    getFundedGranteesMock.mockResolvedValue([]);
    getFundedBudgetsMock.mockResolvedValue([
      {
        id: "b1",
        name: "Confirmed Budget",
        status: "confirmed",
        total_amount: 1000,
        local_currency: "GBP",
        actual_currency: "EUR",
        estimated_exchange_rate: 1,
        owner: { id: "g1", name: "Hope Relief NGO" },
      },
      {
        id: "b2",
        name: "Draft Budget",
        status: "draft",
        total_amount: 500,
        local_currency: "GBP",
        actual_currency: "EUR",
        estimated_exchange_rate: 1,
        owner: { id: "g1", name: "Hope Relief NGO" },
      },
    ]);

    renderDashboard();

    await waitFor(() =>
      expect(screen.getAllByText("Confirmed Budget").length).toBeGreaterThan(0),
    );
    expect(screen.queryByText("Draft Budget")).not.toBeInTheDocument();
    expect(screen.getByText("1 confirmed")).toBeInTheDocument();
  });

  it("shows a muted note instead of a total when there are no confirmed budgets with a usable rate", async () => {
    getFundedBudgetsSummaryMock.mockResolvedValue({
      total_budgets: 1,
      total_allocated_by_currency: [],
    });
    getFundedGranteesMock.mockResolvedValue([
      {
        id: "g1",
        name: "Hope Relief NGO",
        country: "GB",
        budgets_count: 1,
        total_allocated_by_currency: [],
      },
    ]);
    getFundedBudgetsMock.mockResolvedValue([
      {
        id: "b1",
        name: "Clean Water Phase 1",
        status: "confirmed",
        total_amount: 1000,
        local_currency: "GBP",
        owner: { id: "g1", name: "Hope Relief NGO" },
      },
    ]);

    renderDashboard();

    await waitFor(() => expect(screen.getByText("No committed total yet.")).toBeInTheDocument());
    expect(screen.getByText("No committed total yet")).toBeInTheDocument();
  });

  it("shows an empty state when the donor has zero funded budgets", async () => {
    getFundedBudgetsSummaryMock.mockResolvedValue({
      total_budgets: 0,
      total_allocated_by_currency: [],
    });
    getFundedGranteesMock.mockResolvedValue([]);
    getFundedBudgetsMock.mockResolvedValue([]);

    renderDashboard();

    await waitFor(() =>
      expect(screen.getByText("No funded budgets yet")).toBeInTheDocument(),
    );
    expect(screen.queryByText("Grantees")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "View Reports" })).not.toBeInTheDocument();
  });

  it("renders both the desktop table and the mobile card list for funded budgets", async () => {
    getFundedBudgetsSummaryMock.mockResolvedValue({
      total_budgets: 1,
      total_allocated_by_currency: [{ currency: "EUR", total_allocated: 1000 }],
    });
    getFundedGranteesMock.mockResolvedValue([]);
    getFundedBudgetsMock.mockResolvedValue([
      {
        id: "b1",
        name: "Clean Water Phase 1",
        status: "confirmed",
        total_amount: 1000,
        local_currency: "GBP",
        actual_currency: "EUR",
        estimated_exchange_rate: 1,
        owner: { id: "g1", name: "Hope Relief NGO" },
      },
    ]);

    renderDashboard();

    await waitFor(() => expect(screen.getAllByText("Clean Water Phase 1").length).toBe(2));
  });

  it("hides grantees and budgets that are not confirmed from the cards and counts", async () => {
    getFundedBudgetsSummaryMock.mockResolvedValue({
      total_budgets: 3,
      total_allocated_by_currency: [{ currency: "EUR", total_allocated: 1000 }],
    });
    getFundedGranteesMock.mockResolvedValue([
      {
        id: "g1",
        name: "Confirmed NGO",
        country: "GB",
        budgets_count: 2,
        total_allocated_by_currency: [{ currency: "EUR", total_allocated: 1000 }],
      },
      {
        id: "g2",
        name: "Draft Only NGO",
        country: "GB",
        budgets_count: 1,
        total_allocated_by_currency: [],
      },
    ]);
    getFundedBudgetsMock.mockResolvedValue([
      {
        id: "b1",
        name: "Confirmed Budget",
        status: "confirmed",
        total_amount: 1000,
        local_currency: "EUR",
        actual_currency: "EUR",
        estimated_exchange_rate: 1,
        owner: { id: "g1", name: "Confirmed NGO" },
      },
      {
        id: "b2",
        name: "Archived Budget",
        status: "archived",
        total_amount: 500,
        local_currency: "EUR",
        owner: { id: "g1", name: "Confirmed NGO" },
      },
      {
        id: "b3",
        name: "Draft Budget",
        status: "draft",
        total_amount: 500,
        local_currency: "EUR",
        owner: { id: "g2", name: "Draft Only NGO" },
      },
    ]);

    renderDashboard();

    await waitFor(() =>
      expect(screen.getAllByText("Confirmed Budget").length).toBeGreaterThan(0),
    );
    expect(screen.getByText("funded budgets").previousElementSibling).toHaveTextContent("1");
    expect(screen.getByText("grantee organisations").previousElementSibling).toHaveTextContent(
      "1",
    );
    expect(screen.queryByText("Draft Only NGO")).not.toBeInTheDocument();
    expect(screen.getByText("1 budget")).toBeInTheDocument();
  });

  it("falls back to the budget owner's name when the grantee name is missing, and hides a missing country", async () => {
    getFundedBudgetsSummaryMock.mockResolvedValue({
      total_budgets: 1,
      total_allocated_by_currency: [{ currency: "EUR", total_allocated: 1000 }],
    });
    getFundedGranteesMock.mockResolvedValue([
      {
        id: "g1",
        name: null,
        country: null,
        budgets_count: 1,
        total_allocated_by_currency: [{ currency: "EUR", total_allocated: 1000 }],
      },
    ]);
    getFundedBudgetsMock.mockResolvedValue([
      {
        id: "b1",
        name: "Confirmed Budget",
        status: "confirmed",
        total_amount: 1000,
        local_currency: "EUR",
        actual_currency: "EUR",
        estimated_exchange_rate: 1,
        owner: { id: "g1", name: "Hayq Youth Network" },
      },
    ]);

    renderDashboard();

    await waitFor(() =>
      expect(screen.getAllByText("Hayq Youth Network").length).toBeGreaterThan(1),
    );
    expect(screen.getByText("HY")).toBeInTheDocument();
  });
});
