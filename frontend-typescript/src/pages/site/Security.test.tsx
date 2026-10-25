import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import SecurityPage from "./Security";

function renderPage() {
  return render(
    <MemoryRouter>
      <SecurityPage />
    </MemoryRouter>,
  );
}

describe("SecurityPage", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("renders the published sections", () => {
    renderPage();

    expect(
      screen.getByRole("heading", { level: 1, name: "Handled with the care we'd want for our own data." }),
    ).toBeInTheDocument();
    expect(screen.getByText("Can we self-host it?")).toBeInTheDocument();
    expect(screen.getByText("Which AI providers see our data?")).toBeInTheDocument();
    expect(
      screen.getByText("Working in a sensitive or high-risk context?"),
    ).toBeInTheDocument();
  });

  it("labels published answers with an availability pill", () => {
    vi.stubEnv("PROD", true);

    renderPage();

    expect(screen.getAllByText("Available now")).toHaveLength(2);
    expect(screen.getByText("Talk to us")).toBeInTheDocument();
  });

  it("ends with a CTA band linking to the demo request", () => {
    renderPage();

    expect(
      screen.getByRole("heading", { name: "Have a security question we haven't answered?" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Request a demo" })).toHaveAttribute("href", "/contact");
  });

  it("shows the draft GDPR and data-location sections outside production", () => {
    vi.stubEnv("PROD", false);

    renderPage();

    expect(screen.getByText("Is it GDPR compliant?")).toBeInTheDocument();
    expect(screen.getByText("Where is our data stored?")).toBeInTheDocument();
    expect(screen.getAllByText("TBC").length).toBeGreaterThanOrEqual(2);
  });

  it("hides the draft GDPR and data-location sections in production", () => {
    vi.stubEnv("PROD", true);

    renderPage();

    expect(screen.queryByText("Is it GDPR compliant?")).not.toBeInTheDocument();
    expect(screen.queryByText("Where is our data stored?")).not.toBeInTheDocument();
    expect(screen.queryByText("TBC")).not.toBeInTheDocument();
  });
});
