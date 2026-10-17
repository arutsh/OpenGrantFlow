import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import LegalPage from "./Legal";

function renderPage() {
  return render(
    <MemoryRouter>
      <LegalPage />
    </MemoryRouter>,
  );
}

describe("LegalPage", () => {
  it("renders every migrated privacy and terms section", () => {
    renderPage();

    expect(screen.getByRole("heading", { name: "Privacy Policy" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Legal status" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Information we collect" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "How we use it" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Self-hosting" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "How long we keep it" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Third-party processors" })).toBeInTheDocument();

    expect(screen.getByRole("heading", { name: "Terms of Service" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "The service" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "No warranty" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Acceptable use" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Changes to these terms" })).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { name: "Contact" })).toHaveLength(2);
  });

  it("states the current legal status without implying a registered entity", () => {
    renderPage();

    expect(
      screen.getByText(/operated by its maintainer as an open-source project/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/not yet a registered legal entity/),
    ).toBeInTheDocument();
  });

  it("describes retention qualitatively, without a fixed number of days", () => {
    renderPage();

    expect(
      screen.getByText(
        /retain your information only for as long as needed to provide the service/,
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/\d+ days/)).not.toBeInTheDocument();
  });

  it("lists the current subprocessors, noting the Anthropic US transfer", () => {
    renderPage();

    const processors = screen.getByText(/Hetzner \(infrastructure, EU\)/);
    expect(processors).toBeInTheDocument();
    expect(processors.textContent).toContain("Mailjet and MailerSend");
    expect(processors.textContent).toContain("Grafana Cloud");
    expect(processors.textContent).toMatch(/Anthropic.*transfer of data outside the EU\/EEA to the US/);
  });

  it("provides a named contact address alongside the contact form", () => {
    renderPage();

    const privacyEmail = screen.getByRole("link", { name: "privacy@opengrantflow.com" });
    expect(privacyEmail).toHaveAttribute("href", "mailto:privacy@opengrantflow.com");

    const contactLinks = screen.getAllByRole("link", { name: "contact form" });
    expect(contactLinks.length).toBeGreaterThanOrEqual(2);
    for (const link of contactLinks) {
      expect(link).toHaveAttribute("href", "/contact");
    }
  });
});
