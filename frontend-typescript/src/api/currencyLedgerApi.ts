import gatewayApi from "@/api/gatewayApi";
import {
  FundingReceipt,
  FundingReceiptCreate,
  FundingReceiptUpdate,
  CurrencyConversion,
  CurrencyConversionCreate,
  CurrencyConversionUpdate,
  LedgerBalance,
} from "@/pages/Budgets/types/budget";

// Funding receipts

export const createFundingReceipt = async (
  receipt: FundingReceiptCreate
): Promise<FundingReceipt> => {
  const { data } = await gatewayApi.post("/funding-receipts/", receipt);
  return data;
};

export const listFundingReceiptsByBudget = async (
  budgetId: string
): Promise<FundingReceipt[]> => {
  const { data } = await gatewayApi.get(
    `/funding-receipts/by-budget/${budgetId}`
  );
  return data;
};

export const updateFundingReceipt = async (
  receiptId: string,
  receipt: FundingReceiptUpdate
): Promise<FundingReceipt> => {
  const { data } = await gatewayApi.patch(`/funding-receipts/${receiptId}`, receipt);
  return data;
};

export const deleteFundingReceipt = async (receiptId: string): Promise<void> => {
  await gatewayApi.delete(`/funding-receipts/${receiptId}`);
};

// Currency conversions

export const createCurrencyConversion = async (
  conversion: CurrencyConversionCreate
): Promise<CurrencyConversion> => {
  const { data } = await gatewayApi.post("/currency-conversions/", conversion);
  return data;
};

export const listCurrencyConversionsByBudget = async (
  budgetId: string
): Promise<CurrencyConversion[]> => {
  const { data } = await gatewayApi.get(
    `/currency-conversions/by-budget/${budgetId}`
  );
  return data;
};

export const updateCurrencyConversion = async (
  conversionId: string,
  conversion: CurrencyConversionUpdate
): Promise<CurrencyConversion> => {
  const { data } = await gatewayApi.patch(`/currency-conversions/${conversionId}`, conversion);
  return data;
};

export const deleteCurrencyConversion = async (conversionId: string): Promise<void> => {
  await gatewayApi.delete(`/currency-conversions/${conversionId}`);
};

export const resetLedger = async (
  budgetId: string
): Promise<{ receipts_deleted: number; conversions_deleted: number }> => {
  const { data } = await gatewayApi.post(`/currency-conversions/reset/${budgetId}`);
  return data;
};

// Per-currency balance, computed server-side (see LedgerBalance's own
// comment) — the frontend never re-derives this from the raw receipt/
// conversion rows.
export const getLedgerBalance = async (
  budgetId: string
): Promise<LedgerBalance> => {
  const { data } = await gatewayApi.get(
    `/currency-conversions/balance/${budgetId}`
  );
  return data;
};
