import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import AboutPage from "./About";

function renderPage() {
  return render(
    <MemoryRouter>
      <AboutPage />
    </MemoryRouter>,
  );
}

describe("AboutPage", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("renders the hero, origin story, mission, values, model and open-code sections", () => {
    renderPage();

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Grant administration should not consume the capacity that grants exist to create.",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "This started as our own problem, not a business plan" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Our mission" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Our values" })).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent)).toEqual([
      "Security, without making it your problem to think about",
      "Transparency, because trust has to be built on something",
      "Collaboration is the cornerstone of this sector",
      "Free where it matters most",
      "Grassroots: free",
      "Larger institutions: sustain it",
      "Surplus: reinvested",
    ]);
    expect(screen.getByRole("heading", { name: "Open by design" })).toBeInTheDocument();
  });

  it("ends with a CTA band linking to the contact page", () => {
    renderPage();

    expect(screen.getByRole("heading", { name: "See what we have built so far" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Request a demo" })).toHaveAttribute("href", "/contact");
  });

  it("links to the public source code with safe external-link attributes", () => {
    renderPage();

    const github = screen.getByRole("link", { name: "Read the code on GitHub" });
    expect(github).toHaveAttribute("href", "https://github.com/arutsh/OpenGrantFlow");
    expect(github).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("shows the draft CIC set-up section with a TBC marker outside production", () => {
    vi.stubEnv("PROD", false);

    renderPage();

    expect(screen.getByText(/Community Interest Company/)).toBeInTheDocument();
    expect(screen.getByText("TBC")).toBeInTheDocument();
  });

  it("hides the draft CIC set-up section in production", () => {
    vi.stubEnv("PROD", true);

    renderPage();

    expect(document.getElementById("set-up")).not.toBeInTheDocument();
    expect(screen.queryByText(/Community Interest Company/)).not.toBeInTheDocument();
    expect(screen.queryByText("TBC")).not.toBeInTheDocument();
  });
});
