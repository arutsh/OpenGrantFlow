import { renderHook, waitFor } from "@testing-library/react";
import gatewayApi from "@/api/gatewayApi";
import { axiosHttpError, QueryClientWrapper as wrapper } from "@/test/queryClient";
import {
  classifySiteAssistantError,
  useAskSiteAssistant,
  useSiteAssistantConfig,
} from "./siteAssistantApi";

vi.mock("@/api/gatewayApi", () => ({ default: { get: vi.fn(), post: vi.fn() } }));

const getMock = vi.mocked(gatewayApi.get);
const postMock = vi.mocked(gatewayApi.post);

beforeEach(() => {
  getMock.mockReset();
  postMock.mockReset();
});

describe("useSiteAssistantConfig", () => {
  it("returns the config from the ai service", async () => {
    getMock.mockResolvedValue({ data: { enabled: true, max_question_chars: 500 } });

    const { result } = renderHook(() => useSiteAssistantConfig(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({ enabled: true, max_question_chars: 500 });
    expect(getMock).toHaveBeenCalledWith("/ai/site-assistant/config");
  });

  it("does not fetch while disabled", () => {
    renderHook(() => useSiteAssistantConfig({ enabled: false }), { wrapper });

    expect(getMock).not.toHaveBeenCalled();
  });

  it("does not retry a failed config request", async () => {
    getMock.mockRejectedValue(axiosHttpError(503));

    const { result } = renderHook(() => useSiteAssistantConfig(), { wrapper });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(getMock).toHaveBeenCalledTimes(1);
  });
});

describe("useAskSiteAssistant", () => {
  it("posts the question and persona and returns the answer", async () => {
    const answer = {
      answer: "Budgets export to Excel.",
      answerable: true,
      citations: [{ content_id: "a", url: "/how-it-works#export", title: "Export" }],
    };
    postMock.mockResolvedValue({ data: answer });

    const { result } = renderHook(() => useAskSiteAssistant(), { wrapper });
    result.current.mutate({ question: "Can I export?", persona: "funder" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(answer);
    expect(postMock).toHaveBeenCalledWith("/ai/site-assistant/ask", {
      question: "Can I export?",
      persona: "funder",
    });
  });

  it.each([
    [429, "daily_cap"],
    [503, "unavailable"],
    [404, "unavailable"],
    [403, "unavailable"],
    [500, "error"],
  ])("classifies a %i response as %s", async (status, expected) => {
    postMock.mockRejectedValue(axiosHttpError(status));

    const { result } = renderHook(() => useAskSiteAssistant(), { wrapper });
    result.current.mutate({ question: "Hi?", persona: null });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(postMock).toHaveBeenCalledTimes(1);
    expect(classifySiteAssistantError(result.current.error)).toBe(expected);
  });

  it("classifies a network error as a generic error", () => {
    expect(classifySiteAssistantError(new Error("offline"))).toBe("error");
  });
});
