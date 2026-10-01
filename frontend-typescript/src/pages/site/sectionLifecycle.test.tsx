import type { ComponentType } from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "@/context/AuthContext";
import { buildSiteContent, getSection, type SitePage } from "@/lib/siteContent";
import HomePage from "./Home";
import HowItWorksPage from "./HowItWorks";
import SecurityPage from "./Security";
import AboutPage from "./About";
import ContactPage from "./Contact";

vi.mock("@/lib/siteContent", async (importOriginal) => ({
  ...await importOriginal<typeof import("@/lib/siteContent")>(),
  getSection: vi.fn(),
}));

const files = import.meta.glob(
  ["../../content/site/**/*.md", "!../../content/site/README.md"],
  { eager: true, query: "?raw", import: "default" },
) as Record<string, string>;
const sections = [...buildSiteContent(files).sections.values()];
const PAGES: Partial<Record<SitePage, ComponentType>> = {
  home: HomePage,
  "how-it-works": HowItWorksPage,
  security: SecurityPage,
  about: AboutPage,
  contact: ContactPage,
};

describe.each(sections)("$id publication lifecycle", (section) => {
  it.each([false, true])("handles draft content (production: %s)", (isProd) => {
    const changed = Object.fromEntries(Object.entries(files).map(([path, raw]) => [
      path,
      raw.includes(`id: ${section.id}\n`)
        ? raw.replace(/status: (published|draft)/, "status: draft")
        : raw.replace(/status: (published|draft)/, "status: published"),
    ]));
    vi.mocked(getSection).mockImplementation(buildSiteContent(changed, { isProd }).getSection);
    const Page = PAGES[section.page];
    if (!Page) throw new Error(`No page component mapped for "${section.page}"`);
    render(<MemoryRouter><AuthProvider><Page /></AuthProvider></MemoryRouter>);

    if (isProd) {
      expect(document.getElementById(section.anchor)).not.toBeInTheDocument();
      expect(screen.queryByText("TBC")).not.toBeInTheDocument();
    } else {
      expect(document.getElementById(section.anchor)).toBeInTheDocument();
      expect(screen.getByText("TBC")).toBeInTheDocument();
    }
  });
});

it.each([false, true])("removes TBC after publishing security sections (production: %s)", (isProd) => {
  const published = Object.fromEntries(Object.entries(files).map(([path, raw]) => [
    path, raw.replace("status: draft", "status: published"),
  ]));
  vi.mocked(getSection).mockImplementation(buildSiteContent(published, { isProd }).getSection);
  render(<MemoryRouter><SecurityPage /></MemoryRouter>);
  expect(screen.getByText("GDPR compliance")).toBeInTheDocument();
  expect(screen.getByText("Where your data is stored")).toBeInTheDocument();
  expect(screen.queryByText("TBC")).not.toBeInTheDocument();
});

it("renders every sector-validation anecdote, not just the first", () => {
  const withSecondAnecdote = Object.fromEntries(Object.entries(files).map(([path, raw]) => [
    path,
    raw.includes("id: how-it-works.sector-validation\n")
      ? raw.replace("items:\n", "items:\n  - title: Second source\n    body: Second anecdote body.\n")
      : raw,
  ]));
  vi.mocked(getSection).mockImplementation(buildSiteContent(withSecondAnecdote).getSection);
  render(<MemoryRouter><HowItWorksPage /></MemoryRouter>);
  expect(screen.getByText("Second anecdote body.")).toBeInTheDocument();
  expect(screen.getByText(/One leader of a small local nonprofit/)).toBeInTheDocument();
});
