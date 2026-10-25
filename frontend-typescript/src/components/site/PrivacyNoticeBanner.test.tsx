import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "@/App";
import type { PrivacyNotice } from "@/lib/privacyNotice";
import { DISMISSED_KEY, PrivacyNoticeBanner } from "./PrivacyNoticeBanner";

vi.mock("@/api/siteAssistantApi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/siteAssistantApi")>()),
  useSiteAssistantConfig: () => ({ data: { enabled: false, max_question_chars: 500 } }),
}));

const PUBLISHED: PrivacyNotice = {
  status: "published",
  version: "v1",
  body: "Questions are kept for 90 days. [Read our privacy policy](/legal#privacy).",
};

function renderBanner(props: { notice?: PrivacyNotice; isProd?: boolean } = {}) {
  return render(
    <MemoryRouter>
      <PrivacyNoticeBanner notice={PUBLISHED} isProd {...props} />
    </MemoryRouter>,
  );
}

function makeFakeJwt(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "none", typ: "JWT" }));
  const body = btoa(JSON.stringify(payload));
  return `${header}.${body}.signature`;
}

function renderAppAt(path: string) {
  window.history.pushState({}, "", path);
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  );
}

describe("PrivacyNoticeBanner", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows the notice, privacy-policy link and Got it on a first visit", () => {
    renderBanner();

    const banner = screen.getByRole("region", { name: "Privacy notice" });
    expect(banner).toHaveTextContent("Questions are kept for 90 days.");
    expect(screen.getByRole("link", { name: "Read our privacy policy" })).toHaveAttribute(
      "href",
      "/legal#privacy",
    );
    expect(screen.getByRole("button", { name: "Got it" })).toBeInTheDocument();
    expect(screen.getByTestId("privacy-notice-spacer")).toBeInTheDocument();
  });

  it("stays dismissed across a rerender once Got it is pressed", async () => {
    const { unmount } = renderBanner();

    await userEvent.click(screen.getByRole("button", { name: "Got it" }));
    expect(screen.queryByRole("region", { name: "Privacy notice" })).not.toBeInTheDocument();
    expect(screen.queryByTestId("privacy-notice-spacer")).not.toBeInTheDocument();
    expect(localStorage.getItem(DISMISSED_KEY)).toBe("v1");

    unmount();
    renderBanner();
    expect(screen.queryByRole("region", { name: "Privacy notice" })).not.toBeInTheDocument();
  });

  it("shows again when the notice version changes", () => {
    localStorage.setItem(DISMISSED_KEY, "v1");

    renderBanner({ notice: { ...PUBLISHED, version: "v2" } });

    expect(screen.getByRole("region", { name: "Privacy notice" })).toBeInTheDocument();
  });

  it("renders and dismisses for the page view when storage throws", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });

    renderBanner();
    await userEvent.click(screen.getByRole("button", { name: "Got it" }));

    expect(screen.queryByRole("region", { name: "Privacy notice" })).not.toBeInTheDocument();
  });

  it("hides a draft notice in production builds", () => {
    renderBanner({ notice: { ...PUBLISHED, status: "draft" }, isProd: true });

    expect(screen.queryByRole("region", { name: "Privacy notice" })).not.toBeInTheDocument();
  });

  it("marks a draft notice TBC outside production builds", () => {
    renderBanner({ notice: { ...PUBLISHED, status: "draft" }, isProd: false });

    const banner = screen.getByRole("region", { name: "Privacy notice" });
    expect(banner.querySelector("[data-tbc]")).not.toBeNull();
  });

  it("appears on public pages but not on authenticated app routes", async () => {
    const { unmount } = renderAppAt("/legal");
    expect(
      await screen.findByRole("region", { name: "Privacy notice" }),
    ).toBeInTheDocument();
    unmount();

    localStorage.setItem("token", makeFakeJwt({ user_id: "u1", email_verified: true }));
    localStorage.setItem("username", "jane@example.com");
    sessionStorage.setItem("status", "pending");
    renderAppAt("/onboarding");

    expect(await screen.findByText("Tell us about you")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Privacy notice" })).not.toBeInTheDocument();
  });
});
