import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { SiteMarkdown } from "./SiteMarkdown";

function renderMarkdown(body: string) {
  return render(
    <MemoryRouter>
      <SiteMarkdown>{body}</SiteMarkdown>
    </MemoryRouter>,
  );
}

describe("SiteMarkdown", () => {
  it("renders no element for raw HTML in the body", () => {
    const { container } = renderMarkdown("Before <script>alert('x')</script> after.");

    expect(container.querySelector("script")).not.toBeInTheDocument();
  });

  it("renders an internal link as a router link", () => {
    renderMarkdown("[Contact us](/contact)");

    const link = screen.getByRole("link", { name: "Contact us" });
    expect(link).toHaveAttribute("href", "/contact");
    expect(link).not.toHaveAttribute("target");
  });

  it("gives an external link rel=noopener noreferrer", () => {
    renderMarkdown("[Example](https://example.com)");

    const link = screen.getByRole("link", { name: "Example" });
    expect(link).toHaveAttribute("href", "https://example.com");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });
});
