import { createElement, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AxiosError, AxiosHeaders } from "axios";

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

export function withQueryClient(children: ReactNode, client = createTestQueryClient()) {
  return createElement(QueryClientProvider, { client }, children);
}

export function QueryClientWrapper({ children }: { children: ReactNode }) {
  return withQueryClient(children);
}

export function axiosHttpError(status: number) {
  const config = { headers: new AxiosHeaders() };
  return new AxiosError("failed", undefined, config, undefined, {
    status,
    statusText: "",
    data: {},
    headers: {},
    config,
  });
}
