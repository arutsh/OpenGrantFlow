import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { SectionHead } from "./SectionHead";
import { CtaBand } from "./CtaBand";
import { SiteSection } from "./SiteSection";

describe("SectionHead", () => {
  it("renders an h2 by default, with its eyebrow and intro", () => {
    render(<SectionHead eyebrow="What you get back" title="Hours back" intro="Less admin." />);

    expect(screen.getByRole("heading", { level: 2, name: "Hours back" })).toBeInTheDocument();
    expect(screen.getByText("What you get back")).toHaveClass("text-site-eyebrow");
    expect(screen.getByText("Less admin.")).toBeInTheDocument();
  });

  it("renders an h1 page title when asked", () => {
    render(<SectionHead title="How it works" as="h1" />);

    expect(screen.getByRole("heading", { level: 1, name: "How it works" })).toHaveClass(
      "text-site-page-title",
    );
  });

  it("omits the eyebrow when none is given", () => {
    const { container } = render(<SectionHead title="Values" />);

    expect(container.querySelector(".text-site-eyebrow")).not.toBeInTheDocument();
  });
});

describe("CtaBand", () => {
  it("renders an h2, its body and a link to the CTA target", () => {
    render(
      <MemoryRouter>
        <CtaBand
          id="pilot-teaser"
          title="Become a Pilot Partner"
          body="Free for three months."
          cta={{ label: "Request a demo", to: "/contact" }}
        />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("heading", { level: 2, name: "Become a Pilot Partner" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Free for three months.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Request a demo" })).toHaveAttribute(
      "href",
      "/contact",
    );
    expect(document.getElementById("pilot-teaser")?.tagName).toBe("SECTION");
  });
});

describe("SiteSection", () => {
  it("carries its anchor id and an optional mist background", () => {
    const { rerender } = render(<SiteSection id="values">Body</SiteSection>);

    const section = document.getElementById("values");
    expect(section?.tagName).toBe("SECTION");
    expect(section).not.toHaveClass("bg-brand-mist");

    rerender(<SiteSection id="values" alt>Body</SiteSection>);
    expect(document.getElementById("values")).toHaveClass("bg-brand-mist");
  });
});
