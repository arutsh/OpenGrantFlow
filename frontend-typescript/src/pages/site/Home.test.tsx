import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/context/AuthContext";
import gatewayApi from "@/api/gatewayApi";
import { withQueryClient } from "@/test/queryClient";
import HomePage from "./Home";

vi.mock("@/api/gatewayApi", () => ({ default: { get: vi.fn(), post: vi.fn() } }));

const getMock = vi.mocked(gatewayApi.get);

function renderAt(path: string) {
  return render(
    withQueryClient(
      <MemoryRouter initialEntries={[path]}>
        <AuthProvider>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/dashboard" element={<div>Dashboard Page</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    ),
  );
}

describe("HomePage", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    getMock.mockReset();
    getMock.mockResolvedValue({ data: { enabled: false, max_question_chars: 500 } });
  });

  describe("hero", () => {
    const CLASSIC = "Grant management without spreadsheets.";
    const ASK = "One shared financial record. Zero spreadsheets.";
    const FIELD = "Ask a question about Open Grant Flow";

    it("shows a placeholder, and neither hero, while the config is loading", () => {
      getMock.mockReturnValue(new Promise(() => {}));
      renderAt("/");

      expect(screen.getByRole("region", { name: "Loading" })).toHaveAttribute("aria-busy", "true");
      expect(screen.queryByRole("heading", { name: CLASSIC })).not.toBeInTheDocument();
      expect(screen.queryByRole("heading", { name: ASK })).not.toBeInTheDocument();
      expect(screen.queryByLabelText(FIELD)).not.toBeInTheDocument();
      expect(document.getElementById("values-summary")).toBeInTheDocument();
    });

    it("holds the assistant box when the assistant is enabled", async () => {
      getMock.mockResolvedValue({ data: { enabled: true, max_question_chars: 500 } });
      renderAt("/");

      expect(await screen.findByRole("heading", { level: 1, name: ASK })).toBeInTheDocument();
      expect(screen.getByLabelText(FIELD)).toHaveAttribute("maxLength", "500");
      expect(screen.queryByRole("heading", { name: CLASSIC })).not.toBeInTheDocument();
      expect(getMock).toHaveBeenCalledWith("/ai/site-assistant/config");

      const browse = document.getElementById("browse-instead") as HTMLElement;
      expect(browse).toHaveTextContent("Prefer to browse instead?");
      expect(within(browse).getByRole("link", { name: "How it works" })).toHaveAttribute(
        "href",
        "/how-it-works",
      );
      expect(within(browse).getByRole("link", { name: "Security & data" })).toHaveAttribute(
        "href",
        "/security",
      );
      expect(within(browse).getByRole("link", { name: "About" })).toHaveAttribute("href", "/about");
    });

    it("shows the classic hero when the assistant is disabled", async () => {
      renderAt("/");

      expect(await screen.findByRole("heading", { name: CLASSIC })).toBeInTheDocument();
      expect(screen.queryByLabelText(FIELD)).not.toBeInTheDocument();
      expect(document.getElementById("browse-instead")).not.toBeInTheDocument();
    });

    it("shows the classic hero, with no error, when the config request fails", async () => {
      getMock.mockRejectedValue(new Error("network down"));
      renderAt("/");

      expect(await screen.findByRole("heading", { name: CLASSIC })).toBeInTheDocument();
      expect(screen.queryByLabelText(FIELD)).not.toBeInTheDocument();
      expect(screen.queryByText(/went wrong|error|unavailable/i)).not.toBeInTheDocument();
    });
  });

  it("renders the classic hero and its CTAs", async () => {
    renderAt("/");

    expect(
      await screen.findByRole("heading", { name: "Grant management without spreadsheets." }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Become a Pilot Partner" }),
    ).toHaveAttribute("href", "/contact#pilot");
    expect(
      screen.getByRole("link", { name: "See how it works" }),
    ).toHaveAttribute("href", "/how-it-works");
    expect(
      screen.getByRole("img", {
        name: "Open Grant Flow budgets dashboard with the AI budget assistant panel",
      }),
    ).toBeInTheDocument();
  });

  it("does not render the product demo embed", () => {
    const { container } = renderAt("/");

    expect(container.querySelector("iframe")).not.toBeInTheDocument();
    expect(document.getElementById("demo")).not.toBeInTheDocument();
  });

  it("renders the four values and the pilot call-to-action band", () => {
    renderAt("/");

    const values = document.getElementById("values-summary") as HTMLElement;
    expect(within(values).getByRole("heading", { level: 2, name: "Our values" })).toBeInTheDocument();
    expect(within(values).getByText("What we believe")).toBeInTheDocument();
    expect(within(values).getAllByRole("listitem")).toHaveLength(4);

    const band = document.getElementById("pilot-teaser") as HTMLElement;
    expect(
      within(band).getByRole("heading", { level: 2, name: "Become a Pilot Partner" }),
    ).toBeInTheDocument();
    expect(within(band).getByRole("link", { name: "Request a demo" })).toHaveAttribute(
      "href",
      "/contact#pilot",
    );
  });

  it("does not show the old in-development workflow status pills", () => {
    renderAt("/");

    expect(screen.queryByText("Updated Spreadsheet")).not.toBeInTheDocument();
    expect(screen.queryByText("Word Report")).not.toBeInTheDocument();
    expect(screen.queryByText("Corrections")).not.toBeInTheDocument();
    expect(screen.queryByText(/in development/i)).not.toBeInTheDocument();
  });

  it("does not offer login/sign-up/get-started anywhere on the page", () => {
    renderAt("/");

    expect(screen.queryByText(/sign up/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^log in$/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/get started/i)).not.toBeInTheDocument();
  });

  it("redirects to /dashboard when authenticated", () => {
    localStorage.setItem("token", "fake-token");
    localStorage.setItem("username", "john");

    renderAt("/");

    expect(screen.getByText("Dashboard Page")).toBeInTheDocument();
    expect(getMock).not.toHaveBeenCalled();
    expect(
      screen.queryByText("Grant management without spreadsheets."),
    ).not.toBeInTheDocument();
  });

  describe("legacy hash redirects", () => {
    function renderWithHash(hash: string) {
      return render(
        withQueryClient(
          <MemoryRouter initialEntries={[`/${hash}`]}>
            <AuthProvider>
              <Routes>
                <Route path="/" element={<HomePage />} />
                <Route path="/contact" element={<div>Contact Page</div>} />
                <Route path="/about" element={<div>About Page</div>} />
                <Route path="/how-it-works" element={<div>How it works Page</div>} />
              </Routes>
            </AuthProvider>
          </MemoryRouter>,
        ),
      );
    }

    it.each([
      ["#contact", "Contact Page"],
      ["#about", "About Page"],
      ["#vision", "About Page"],
      ["#platform", "How it works Page"],
      ["#problem", "How it works Page"],
      ["#founding-partners", "Contact Page"],
    ])("redirects %s to the page that now holds that content", async (hash, expectedPage) => {
      renderWithHash(hash);

      await waitFor(() => {
        expect(screen.getByText(expectedPage)).toBeInTheDocument();
      });
    });
  });
});
