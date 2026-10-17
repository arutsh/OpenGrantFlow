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
      screen.getByText("Handled with the care we'd want for our own data"),
    ).toBeInTheDocument();
    expect(screen.getByText("Self-hosting")).toBeInTheDocument();
    expect(screen.getByText("AI providers and data")).toBeInTheDocument();
    expect(
      screen.getByText("Talk to us about your security needs"),
    ).toBeInTheDocument();
  });

  it("shows the draft GDPR and data-location sections outside production", () => {
    vi.stubEnv("PROD", false);

    renderPage();

    expect(screen.getByText("GDPR compliance")).toBeInTheDocument();
    expect(screen.getByText("Where your data is stored")).toBeInTheDocument();
    expect(screen.getAllByText("TBC").length).toBeGreaterThanOrEqual(2);
  });

  it("hides the draft GDPR and data-location sections in production", () => {
    vi.stubEnv("PROD", true);

    renderPage();

    expect(screen.queryByText("GDPR compliance")).not.toBeInTheDocument();
    expect(screen.queryByText("Where your data is stored")).not.toBeInTheDocument();
    expect(screen.queryByText("TBC")).not.toBeInTheDocument();
  });
});
