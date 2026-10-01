import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import PublicLayout from "./PublicLayout";

function HowItWorksStub() {
  return (
    <div>
      <p>How it works intro</p>
      <section id="five-steps">Five steps section</section>
    </div>
  );
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<PublicLayout />}>
          <Route path="/" element={<div>Home page</div>} />
          <Route path="/how-it-works" element={<HowItWorksStub />} />
          <Route
            path="/legal"
            element={<section id="privacy">Privacy section</section>}
          />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("PublicLayout", () => {
  it("exposes all nav links and Request Demo once the mobile toggle is opened", async () => {
    renderAt("/");

    await userEvent.click(
      screen.getByRole("button", { name: "Toggle navigation menu" }),
    );

    const mobileNav = within(screen.getByRole("navigation", { name: "Mobile" }));
    expect(mobileNav.getByRole("link", { name: "How it works" })).toBeInTheDocument();
    expect(mobileNav.getByRole("link", { name: "Security" })).toBeInTheDocument();
    expect(mobileNav.getByRole("link", { name: "About" })).toBeInTheDocument();
    expect(mobileNav.getByRole("link", { name: "Contact" })).toBeInTheDocument();
    expect(mobileNav.getByRole("link", { name: "Request Demo" })).toBeInTheDocument();
  });

  it("scrolls to the section named by the URL hash", () => {
    const scrollIntoViewSpy = vi.fn();
    vi.spyOn(Element.prototype, "scrollIntoView").mockImplementation(
      scrollIntoViewSpy,
    );

    renderAt("/how-it-works#five-steps");

    expect(scrollIntoViewSpy).toHaveBeenCalled();

    vi.restoreAllMocks();
  });

  it("links the privacy policy and terms footer entries to /legal", () => {
    renderAt("/");

    expect(screen.getByRole("link", { name: "Privacy Policy" })).toHaveAttribute(
      "href",
      "/legal#privacy",
    );
    expect(screen.getByRole("link", { name: "Terms" })).toHaveAttribute(
      "href",
      "/legal#terms",
    );
  });

  it("scrolls to the legal anchor when a footer link is followed from another page", async () => {
    const scrolledIds: string[] = [];
    vi.spyOn(Element.prototype, "scrollIntoView").mockImplementation(function (
      this: Element,
    ) {
      scrolledIds.push(this.id);
    });

    renderAt("/how-it-works");
    await userEvent.click(screen.getByRole("link", { name: "Privacy Policy" }));

    expect(screen.getByText("Privacy section")).toBeInTheDocument();
    expect(scrolledIds).toContain("privacy");

    vi.restoreAllMocks();
  });
});
