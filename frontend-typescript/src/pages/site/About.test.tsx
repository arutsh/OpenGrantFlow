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

  it("renders the mission, origin story, values and open-code sections", () => {
    renderPage();

    expect(
      screen.getByRole("heading", {
        name: "Grant management should be collaborative, not administrative",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Built from lived experience" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "What we value" })).toBeInTheDocument();
    expect(screen.getByText("Transparency")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Open by design" })).toBeInTheDocument();
  });

  it("links to the public source code with safe external-link attributes", () => {
    renderPage();

    const github = screen.getByRole("link", { name: "GitHub" });
    expect(github).toHaveAttribute("href", "https://github.com/arutsh/OpenGrantFlow");
    expect(github).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("shows the draft CIC set-up section with a TBC marker outside production", () => {
    vi.stubEnv("PROD", false);

    renderPage();

    expect(screen.getByText("How we are set up")).toBeInTheDocument();
    expect(screen.getByText("TBC")).toBeInTheDocument();
  });

  it("hides the draft CIC set-up section in production", () => {
    vi.stubEnv("PROD", true);

    renderPage();

    expect(screen.queryByText("How we are set up")).not.toBeInTheDocument();
    expect(screen.queryByText(/Community Interest Company/)).not.toBeInTheDocument();
    expect(screen.queryByText("TBC")).not.toBeInTheDocument();
  });
});
