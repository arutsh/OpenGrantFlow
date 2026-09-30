import gatewayApi from "@/api/gatewayApi";

export interface ProviderKeyConfig {
  id: string;
  provider: string;
  label: string | null;
  model: string | null;
  masked_key: string | null;
  base_url: string | null;
  is_default: boolean;
}

export interface ApprovedEndpoint {
  origin: string;
  label: string;
}

export interface AiSettings {
  configs: ProviderKeyConfig[];
  platform_fallback_enabled: boolean;
  approved_endpoints: ApprovedEndpoint[];
}

export const getAiSettings = async (): Promise<AiSettings> => {
  const { data } = await gatewayApi.get("/users/me/ai-settings");
  return data;
};

export interface CreateAiKeyParams {
  provider: string;
  label?: string | null;
  key?: string | null;
  model: string;
  base_url?: string | null;
  is_default?: boolean;
}

export const createAiKey = async (
  params: CreateAiKeyParams,
): Promise<AiSettings> => {
  const { data } = await gatewayApi.post("/users/me/ai-settings/keys", params);
  return data;
};

export const setDefaultAiKey = async (configId: string): Promise<AiSettings> => {
  const { data } = await gatewayApi.post(
    `/users/me/ai-settings/keys/${configId}/default`,
  );
  return data;
};

export interface DeleteAiKeyParams {
  new_default_id?: string;
}

export const deleteAiKey = async (
  configId: string,
  params?: DeleteAiKeyParams,
): Promise<AiSettings> => {
  const { data } = await gatewayApi.delete(`/users/me/ai-settings/keys/${configId}`, {
    data: params,
  });
  return data;
};

export const setPlatformFallback = async (enabled: boolean): Promise<AiSettings> => {
  const { data } = await gatewayApi.put("/users/me/ai-settings/platform-fallback", {
    enabled,
  });
  return data;
};
