import {
  BudgetUpdate,
  Budget,
  BudgetPatched,
  CreateBudgetWithLinesRequest,
  DonorTemplate,
} from "@/pages/Budgets/types/budget";
import gatewayApi from "@/api/gatewayApi";

export const editBudget = async (
  id: string,
  budgetData: BudgetUpdate
): Promise<Budget> => {
  const { data } = await gatewayApi.patch(`/budgets/${id}`, budgetData);
  return data;
};

export const deleteBudget = async (id: string) => {
  const { data } = await gatewayApi.delete(`/budgets/${id}`);
  return data;
};

export const archiveBudget = async (id: string) => {
  const { data } = await gatewayApi.patch(`/budgets/${id}`, {
    status: "archived",
  });
  return data;
};

export const restoreBudget = async (id: string): Promise<BudgetPatched> => {
  const { data } = await gatewayApi.post(`/budgets/${id}/restore`);
  return data;
};

export const createBudget = async (
  budgetData: BudgetUpdate
): Promise<Budget> => {
  const { data } = await gatewayApi.post(`/budgets/`, budgetData);
  return data;
};

export const createBudgetWithLines = async (
  req: CreateBudgetWithLinesRequest
): Promise<Budget> => {
  const { data } = await gatewayApi.post("/budgets/with-lines", req);
  return data;
};

export const importBudgetFromExcel = async (file: File): Promise<Budget> => {
  // Chat service orchestrates this now, not budget — the drop-box UI itself is unchanged.
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await gatewayApi.post("/chat/import-excel", formData);
  return data;
};

export const saveBudgetAsTemplate = async (
  budgetId: string,
  name: string
): Promise<DonorTemplate> => {
  const { data } = await gatewayApi.post(`/budgets/${budgetId}/save-as-template`, {
    name,
  });
  return data;
};

// Streams the workbook bytes directly, unlike downloadAttachment's presigned-URL redirect.
export const exportBudgetWorkbook = async (budgetId: string): Promise<Blob> => {
  const { data } = await gatewayApi.get(`/budgets/${budgetId}/export.xlsx`, {
    responseType: "blob",
  });
  return data;
};
