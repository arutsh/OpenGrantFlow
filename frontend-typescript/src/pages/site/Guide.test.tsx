import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import GuidePage from "./Guide";
import { getGuideDoc, resolveGuideHref, slugifyHeading } from "@/lib/guideDocs";

function renderGuide(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/" element={<p>home</p>} />
        <Route path="/guides/:slug" element={<GuidePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("slugifyHeading", () => {
  it.each([
    ["1. Getting Started", "1-getting-started"],
    ["Who It's For", "who-its-for"],
    ["Reports & receipts", "reports-receipts"],
    ["  --Edge  case--  ", "edge-case"],
  ])("slugifies %j like the ai service ingester", (heading, expected) => {
    expect(slugifyHeading(heading)).toBe(expected);
  });
});

describe("resolveGuideHref", () => {
  const repo = "https://github.com/arutsh/OpenGrantFlow";
  it.each([
    ["./donor-guide.md", "ngo-guide", "/guides/donor-guide"],
    ["./ngo-guide.md#7-exporting-to-excel", "donor-guide", "/guides/ngo-guide#7-exporting-to-excel"],
    ["./README.md#24-ai", "ngo-guide", `${repo}/blob/main/docs/user-guide/README.md#24-ai`],
    ["../../issues", "product", `${repo}/issues`],
    ["../../blob/main/README.md#contributing", "product", `${repo}/blob/main/README.md#contributing`],
    ["#4-understanding", "ngo-guide", "#4-understanding"],
    ["https://linkedin.com/in/x", "product", "https://linkedin.com/in/x"],
  ])("maps %s in %s to %s", (href, slug, expected) => {
    expect(resolveGuideHref(href, slug)).toBe(expected);
  });

  it("renders the ngo guide's sibling-guide link as an internal route", () => {
    renderGuide("/guides/ngo-guide");
    expect(screen.getAllByRole("link", { name: "Donor / Funder Guide" })[0]).toHaveAttribute(
      "href",
      "/guides/donor-guide",
    );
  });
});

describe("GuidePage", () => {
  it.each(["ngo-guide", "donor-guide", "product"])(
    "gives every H2 in %s an anchor matching its indexed chunk URL",
    (slug) => {
      const raw = getGuideDoc(slug);
      expect(raw).not.toBeNull();
      renderGuide(`/guides/${slug}`);

      const headings = [...raw!.matchAll(/^## (?!#)(.+)$/gm)].map((m) => m[1].trim());
      expect(headings.length).toBeGreaterThan(0);
      for (const heading of headings) {
        const el = document.getElementById(slugifyHeading(heading));
        expect(el?.tagName).toBe("H2");
        expect(el).toHaveTextContent(heading.replace(/[*_`]/g, ""));
      }
    },
  );

  it.each([
    ["ngo-guide", "4-understanding-the-currencies-on-a-budget"],
    ["donor-guide", "1-approving-grantees"],
    ["product", "who-its-for"],
  ])("renders /guides/%s#%s at the right section", (slug, anchor) => {
    renderGuide(`/guides/${slug}#${anchor}`);
    expect(document.getElementById(anchor)?.tagName).toBe("H2");
  });

  it("redirects an unknown guide slug home", () => {
    renderGuide("/guides/nope");
    expect(screen.getByText("home")).toBeInTheDocument();
  });

  it("does not expose the user-guide README as a guide", () => {
    expect(getGuideDoc("readme")).toBeNull();
  });
});
