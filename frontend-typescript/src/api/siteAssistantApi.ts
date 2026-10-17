import { isAxiosError } from "axios";
import { useMutation, useQuery } from "@tanstack/react-query";
import gatewayApi from "@/api/gatewayApi";

export type SiteAssistantPersona = "grantee" | "funder" | "technical";

export interface SiteAssistantConfig {
  enabled: boolean;
  max_question_chars: number;
}

export interface SiteAssistantCitation {
  content_id: string;
  url: string;
  title: string;
}

export interface SiteAssistantAnswer {
  answer: string;
  answerable: boolean;
  citations: SiteAssistantCitation[];
}

export interface AskSiteAssistantParams {
  question: string;
  persona: SiteAssistantPersona | null;
}

export type SiteAssistantFailure = "daily_cap" | "unavailable" | "error";

export const getSiteAssistantConfig = async (): Promise<SiteAssistantConfig> => {
  const { data } = await gatewayApi.get("/ai/site-assistant/config");
  return data;
};

export const askSiteAssistant = async (
  params: AskSiteAssistantParams,
): Promise<SiteAssistantAnswer> => {
  const { data } = await gatewayApi.post("/ai/site-assistant/ask", params);
  return data;
};

// 404 = switched off since config loaded; 403 = verifier rejected us (no token is sent yet).
const UNAVAILABLE_STATUSES = new Set([403, 404, 503]);

export function classifySiteAssistantError(error: unknown): SiteAssistantFailure {
  const status = isAxiosError(error) ? error.response?.status : undefined;
  if (status === 429) return "daily_cap";
  if (status !== undefined && UNAVAILABLE_STATUSES.has(status)) return "unavailable";
  return "error";
}

export function useSiteAssistantConfig({ enabled = true }: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ["siteAssistant", "config"],
    queryFn: getSiteAssistantConfig,
    enabled,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
}

export function useAskSiteAssistant() {
  return useMutation({ mutationFn: askSiteAssistant, retry: false });
}
