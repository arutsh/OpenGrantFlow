import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/context/AuthContext";
import HomePage from "./Home";

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/dashboard" element={<div>Dashboard Page</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("HomePage", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it("renders the hero and its CTAs", () => {
    renderAt("/");

    expect(
      screen.getByRole("heading", { name: "Grant management without spreadsheets." }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Become a Pilot Partner" }),
    ).toHaveAttribute("href", "/contact#pilot");
    expect(
      screen.getByRole("link", { name: "See how it works" }),
    ).toHaveAttribute("href", "/how-it-works");
  });

  it("renders the product demo embed", () => {
    renderAt("/");

    const demoFrame = screen.getByTitle(
      "OpenGrantFlow - Grant Management Without Spreadsheets",
    );
    expect(demoFrame.tagName).toBe("IFRAME");
    expect(document.getElementById("demo")).toContainElement(demoFrame);
    expect(demoFrame).toHaveAttribute(
      "src",
      expect.stringContaining(
        "https://demo.arcade.software/video/bJX6Bh5bfgTZU5E2pUSK",
      ),
    );
    expect(demoFrame).toHaveAttribute("loading", "lazy");
  });

  it("offers links to browse the rest of the site", () => {
    renderAt("/");

    expect(
      screen.getByRole("link", { name: /How it works/ }),
    ).toHaveAttribute("href", "/how-it-works");
    expect(
      screen.getByRole("link", { name: /Security & data/ }),
    ).toHaveAttribute("href", "/security");
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
    expect(
      screen.queryByText("Grant management without spreadsheets."),
    ).not.toBeInTheDocument();
  });

  describe("legacy hash redirects", () => {
    function renderWithHash(hash: string) {
      return render(
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
