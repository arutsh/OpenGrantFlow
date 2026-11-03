import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { vi, type Mock } from "vitest";
import Dashboard from "./Dashboard";
import { AuthProvider } from "@/context/AuthContext";
import * as dashboardApi from "@/api/dashboardApi";
import { GranteeDashboardSummary } from "@/api/dashboardApi";
import * as donorDashboardApi from "@/api/donorDashboardApi";
import * as usersApi from "@/api/usersApi";

vi.mock("@/api/usersApi", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/usersApi")>();
  return {
    ...actual,
    getUserProfile: vi.fn(),
  };
});
const getUserProfileMock = usersApi.getUserProfile as unknown as Mock;

vi.mock("@/api/dashboardApi", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/dashboardApi")>();
  return {
    ...actual,
    getGranteeDashboardSummary: vi.fn(),
  };
});

vi.mock("@/api/donorDashboardApi", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/api/donorDashboardApi")>();
  return {
    ...actual,
    getFundedBudgetsSummary: vi.fn(),
    getFundedGrantees: vi.fn(),
    getFundedBudgets: vi.fn(),
  };
});

const getGranteeDashboardSummaryMock =
  dashboardApi.getGranteeDashboardSummary as unknown as Mock;
const getFundedBudgetsSummaryMock =
  donorDashboardApi.getFundedBudgetsSummary as unknown as Mock;
const getFundedGranteesMock =
  donorDashboardApi.getFundedGrantees as unknown as Mock;
const getFundedBudgetsMock =
  donorDashboardApi.getFundedBudgets as unknown as Mock;

function makeFakeJwt(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "none", typ: "JWT" }));
  const body = btoa(JSON.stringify(payload));
  return `${header}.${body}.signature`;
}

function loginAs(roles: { is_ngo?: boolean; is_donor?: boolean }) {
  localStorage.setItem("token", makeFakeJwt(roles));
  localStorage.setItem("username", "jane");
}

function makeSummary(
  overrides: Partial<GranteeDashboardSummary> = {},
): GranteeDashboardSummary {
  return {
    budget_counts_by_status: [
      { status: "draft", count: 2 },
      { status: "confirmed", count: 3 },
    ],
    committed_by_currency: [{ currency: "EUR", total_allocated: 10000 }],
    received_by_currency: [{ currency: "EUR", total_allocated: 4000 }],
    conversion_progress_by_currency: [
      { currency: "EUR", received: 4000, converted: 2000, percent: 50 },
    ],
    budget_breakdown: [
      {
        budget_id: "b1",
        budget_name: "Clean Water Initiative",
        external_funder_name: "Acme Foundation",
        local_currency: "GBP",
        converted: 1600,
        spent: 600,
        remaining: 1000,
      },
    ],
    ...overrides,
  };
}

function stubDonorApisEmpty() {
  getFundedBudgetsSummaryMock.mockResolvedValue({
    total_budgets: 0,
    total_allocated_by_currency: [],
  });
  getFundedGranteesMock.mockResolvedValue([]);
  getFundedBudgetsMock.mockResolvedValue([]);
}

function renderDashboard() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AuthProvider>
          <Dashboard />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Dashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    stubDonorApisEmpty();
  });

  describe("role-based view (no toggle for single-role accounts)", () => {
    it("shows only the grantee dashboard, no toggle, for an NGO-only account", async () => {
      loginAs({ is_ngo: true });
      getGranteeDashboardSummaryMock.mockResolvedValue(makeSummary());
      renderDashboard();

      await waitFor(() => expect(screen.getByText("EUR")).toBeInTheDocument());
      expect(
        screen.queryByRole("tablist", { name: "Dashboard view" }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByText("Everything you fund, in one place."),
      ).not.toBeInTheDocument();
    });

    it("shows only the donor dashboard, no toggle, for a donor-only account", async () => {
      loginAs({ is_donor: true });
      getFundedBudgetsSummaryMock.mockResolvedValue({
        total_budgets: 1,
        total_allocated_by_currency: [
          { currency: "GBP", total_allocated: 1000 },
        ],
      });
      getFundedGranteesMock.mockResolvedValue([]);
      getFundedBudgetsMock.mockResolvedValue([
        {
          id: "b1",
          name: "Clean Water Phase 1",
          status: "confirmed",
          total_amount: 1000,
          local_currency: "GBP",
          owner: { id: "g1", name: "Some Grantee" },
        },
      ]);
      renderDashboard();

      await waitFor(() =>
        expect(
          screen.getByText("Everything you fund, in one place."),
        ).toBeInTheDocument(),
      );
      expect(
        screen.queryByRole("tablist", { name: "Dashboard view" }),
      ).not.toBeInTheDocument();
      // Grantee-only content (committed/received currency cards) never renders.
      expect(
        screen.queryByText("Confirmed, Received & Converted"),
      ).not.toBeInTheDocument();
    });

    it("shows the toggle and defaults to the grantee view for an account with both roles", async () => {
      loginAs({ is_ngo: true, is_donor: true });
      getGranteeDashboardSummaryMock.mockResolvedValue(makeSummary());
      renderDashboard();

      expect(
        screen.getByRole("tablist", { name: "Dashboard view" }),
      ).toBeInTheDocument();
      await waitFor(() =>
        expect(
          screen.getByText("Confirmed, Received & Converted"),
        ).toBeInTheDocument(),
      );
      expect(screen.getByRole("tab", { name: "Grantee" })).toHaveAttribute(
        "aria-selected",
        "true",
      );
    });

    it("switches to the donor view when the toggle is clicked, and back again", async () => {
      loginAs({ is_ngo: true, is_donor: true });
      getGranteeDashboardSummaryMock.mockResolvedValue(makeSummary());
      getFundedBudgetsSummaryMock.mockResolvedValue({
        total_budgets: 1,
        total_allocated_by_currency: [
          { currency: "GBP", total_allocated: 1000 },
        ],
      });
      getFundedGranteesMock.mockResolvedValue([]);
      getFundedBudgetsMock.mockResolvedValue([]);
      const user = userEvent.setup();
      renderDashboard();

      await waitFor(() =>
        expect(
          screen.getByText("Confirmed, Received & Converted"),
        ).toBeInTheDocument(),
      );

      await user.click(screen.getByRole("tab", { name: "Donor" }));

      await waitFor(() =>
        expect(
          screen.getByText("Everything you fund, in one place."),
        ).toBeInTheDocument(),
      );
      expect(
        screen.queryByText("Confirmed, Received & Converted"),
      ).not.toBeInTheDocument();

      await user.click(screen.getByRole("tab", { name: "Grantee" }));

      await waitFor(() =>
        expect(
          screen.getByText("Confirmed, Received & Converted"),
        ).toBeInTheDocument(),
      );
    });
  });

  describe("grantee dashboard content", () => {
    beforeEach(() => {
      loginAs({ is_ngo: true });
    });

    it("renders real budget-status counts as a composition legend, not mock data", async () => {
      getGranteeDashboardSummaryMock.mockResolvedValue(makeSummary());
      renderDashboard();

      await waitFor(() =>
        expect(screen.getByText(/Draft · 2/)).toBeInTheDocument(),
      );
      expect(screen.getByText(/Confirmed · 3/)).toBeInTheDocument();
      // Total budgets figure (2 draft + 3 confirmed).
      expect(screen.getByText("5")).toBeInTheDocument();
      // The old hardcoded mock values are gone.
      expect(screen.queryByText("Total Budgets")).not.toBeInTheDocument();
      expect(screen.queryByText("Over Budget")).not.toBeInTheDocument();
    });

    it("shows committed, received, and conversion progress for a currency", async () => {
      getGranteeDashboardSummaryMock.mockResolvedValue(makeSummary());
      renderDashboard();

      await waitFor(() => expect(screen.getByText("EUR")).toBeInTheDocument());
      expect(screen.getByText("€10,000")).toBeInTheDocument();
      expect(screen.getByText("€4,000")).toBeInTheDocument();
      expect(screen.getByText(/€2,000/)).toBeInTheDocument();
      expect(screen.getByText(/50%/)).toBeInTheDocument();
    });

    it("renders multiple currencies as separate figures, not blended", async () => {
      getGranteeDashboardSummaryMock.mockResolvedValue(
        makeSummary({
          committed_by_currency: [
            { currency: "EUR", total_allocated: 10000 },
            { currency: "USD", total_allocated: 5000 },
          ],
          received_by_currency: [
            { currency: "EUR", total_allocated: 4000 },
            { currency: "USD", total_allocated: 2000 },
          ],
          conversion_progress_by_currency: [
            { currency: "EUR", received: 4000, converted: 2000, percent: 50 },
            { currency: "USD", received: 2000, converted: 1000, percent: 50 },
          ],
        }),
      );
      renderDashboard();

      await waitFor(() => expect(screen.getByText("EUR")).toBeInTheDocument());
      expect(screen.getByText("USD")).toBeInTheDocument();
      expect(screen.getByText("€10,000")).toBeInTheDocument();
      expect(screen.getByText("US$5,000")).toBeInTheDocument();
    });

    it("renders the per-budget breakdown table with one row per confirmed budget", async () => {
      getGranteeDashboardSummaryMock.mockResolvedValue(
        makeSummary({
          budget_breakdown: [
            {
              budget_id: "b1",
              budget_name: "Clean Water Initiative",
              external_funder_name: "Acme Foundation",
              local_currency: "GBP",
              converted: 1600,
              spent: 600,
              remaining: 1000,
            },
            {
              budget_id: "b2",
              budget_name: "School Rebuild",
              external_funder_name: "Beta Trust",
              local_currency: "GBP",
              converted: 2000,
              spent: 500,
              remaining: 1500,
            },
          ],
        }),
      );
      renderDashboard();

      await waitFor(() =>
        expect(screen.getByText("Clean Water Initiative")).toBeInTheDocument(),
      );
      expect(screen.getByText("School Rebuild")).toBeInTheDocument();
      expect(screen.getByText("Acme Foundation")).toBeInTheDocument();
      expect(screen.getByText("Beta Trust")).toBeInTheDocument();
      expect(screen.getByText("£1,000")).toBeInTheDocument();
      expect(screen.getByText("£1,500")).toBeInTheDocument();
    });

    it("shows an empty-state message when there are no confirmed budgets yet", async () => {
      getGranteeDashboardSummaryMock.mockResolvedValue(
        makeSummary({
          committed_by_currency: [],
          received_by_currency: [],
          conversion_progress_by_currency: [],
          budget_breakdown: [],
        }),
      );
      renderDashboard();

      await waitFor(() =>
        expect(
          screen.getByText("No confirmed budgets with a donor currency yet."),
        ).toBeInTheDocument(),
      );
      expect(screen.getByText("No confirmed budgets yet.")).toBeInTheDocument();
    });
  });

  describe("greeting", () => {
    it("greets the user by their registered first name", async () => {
      localStorage.setItem("token", makeFakeJwt({ is_ngo: true, user_id: "u1" }));
      localStorage.setItem("username", "toby+demo@example.com");
      getUserProfileMock.mockResolvedValue({
        id: "u1",
        first_name: "Toby",
        email: "toby+demo@example.com",
      });
      getGranteeDashboardSummaryMock.mockResolvedValue(makeSummary());
      renderDashboard();

      await waitFor(() => expect(screen.getByText(/Hi Toby/)).toBeInTheDocument());
      expect(getUserProfileMock).toHaveBeenCalledWith("u1");
      expect(screen.queryByText(/toby\+demo@example\.com/)).not.toBeInTheDocument();
    });

    it("falls back to 'Hi there' instead of the email when no first name is available", async () => {
      localStorage.setItem("token", makeFakeJwt({ is_ngo: true, user_id: "u1" }));
      localStorage.setItem("username", "toby+demo@example.com");
      getUserProfileMock.mockResolvedValue({ id: "u1", first_name: null, email: "x" });
      getGranteeDashboardSummaryMock.mockResolvedValue(makeSummary());
      renderDashboard();

      await waitFor(() => expect(screen.getByText(/Hi there/)).toBeInTheDocument());
      expect(screen.queryByText(/toby\+demo@example\.com/)).not.toBeInTheDocument();
    });
  });
});
