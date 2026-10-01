import { test, expect } from "@playwright/test";
import { onboardedApiContext } from "../../support/auth";

// SQLite unit tests can't prove exact storage; this runs against the real Postgres stack.
test("money is stored exactly on Postgres and returned as JSON numbers", async ({
  request,
  baseURL,
}) => {
  const authed = await onboardedApiContext(request, baseURL);

  try {
    const createBudgetRes = await authed.post("/api/v1/budgets/", {
      data: {
        name: `E2E Precision ${crypto.randomUUID()}`,
        external_funder_name: "E2E Funder",
        local_currency: "KES",
        actual_currency: "EUR",
        donor_total_amount: 1234567.89,
        estimated_exchange_rate: 0.0073125123,
      },
    });
    expect(createBudgetRes.status()).toBe(200);
    const budgetId: string = (await createBudgetRes.json()).id;

    for (const amount of [0.1, 0.2]) {
      const addLineRes = await authed.post("/api/v1/budget-lines/", {
        data: { budget_id: budgetId, description: `Line ${amount}`, amount },
      });
      expect(addLineRes.status()).toBe(200);
    }

    const getBudgetRes = await authed.get(`/api/v1/budgets/${budgetId}`);
    expect(getBudgetRes.status()).toBe(200);
    const raw = await getBudgetRes.text();
    const budget = JSON.parse(raw);

    // Float storage would sum to 0.30000000000000004.
    expect(budget.total_amount).toBe(0.3);
    expect(raw).toContain('"total_amount":0.3,');
    expect(budget.estimated_exchange_rate).toBe(0.0073125123);
    expect(budget.donor_total_amount).toBe(1234567.89);
    for (const line of budget.lines) {
      expect(typeof line.amount).toBe("number");
    }

    const deleteBudgetRes = await authed.delete(`/api/v1/budgets/${budgetId}`);
    expect(deleteBudgetRes.status()).toBe(200);
  } finally {
    await authed.dispose();
  }
});
