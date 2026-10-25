import type { ComponentType } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import gatewayApi from "@/api/gatewayApi";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "@/context/AuthContext";
import { buildSiteContent, getSection, type SitePage } from "@/lib/siteContent";
import HomePage from "./Home";
import HowItWorksPage from "./HowItWorks";
import SecurityPage from "./Security";
import AboutPage from "./About";
import ContactPage from "./Contact";
import LegalPage from "./Legal";
import { withQueryClient } from "@/test/queryClient";

vi.mock("@/api/gatewayApi", () => ({
  default: { get: vi.fn().mockResolvedValue({ data: { enabled: false } }) },
}));

vi.mock("@/lib/siteContent", async (importOriginal) => ({
  ...await importOriginal<typeof import("@/lib/siteContent")>(),
  getSection: vi.fn(),
}));

const files = import.meta.glob(
  ["../../content/site/**/*.md", "!../../content/site/README.md"],
  { eager: true, query: "?raw", import: "default" },
) as Record<string, string>;
const sections = [...buildSiteContent(files).sections.values()];
// These Home sections only render inside the assistant hero.
const ASSISTANT_SECTIONS = new Set(["home.ask-hero", "home.browse-instead"]);
const PAGES: Partial<Record<SitePage, ComponentType>> = {
  home: HomePage,
  "how-it-works": HowItWorksPage,
  security: SecurityPage,
  about: AboutPage,
  contact: ContactPage,
  legal: LegalPage,
};

describe.each(sections)("$id publication lifecycle", (section) => {
  it.each([false, true])("handles draft content (production: %s)", async (isProd) => {
    vi.mocked(gatewayApi.get).mockResolvedValue({
      data: { enabled: ASSISTANT_SECTIONS.has(section.id), max_question_chars: 500 },
    });
    const changed = Object.fromEntries(Object.entries(files).map(([path, raw]) => [
      path,
      raw.includes(`id: ${section.id}\n`)
        ? raw.replace(/status: (published|draft)/, "status: draft")
        : raw.replace(/status: (published|draft)/, "status: published"),
    ]));
    vi.mocked(getSection).mockImplementation(buildSiteContent(changed, { isProd }).getSection);
    const Page = PAGES[section.page];
    if (!Page) throw new Error(`No page component mapped for "${section.page}"`);
    render(withQueryClient(<MemoryRouter><AuthProvider><Page /></AuthProvider></MemoryRouter>));
    await waitFor(() =>
      expect(screen.queryByRole("region", { name: "Loading" })).not.toBeInTheDocument(),
    );

    if (isProd) {
      expect(document.getElementById(section.anchor)).not.toBeInTheDocument();
      expect(screen.queryByText("TBC")).not.toBeInTheDocument();
    } else {
      expect(document.getElementById(section.anchor)).toBeInTheDocument();
      expect(screen.getByText("TBC")).toBeInTheDocument();
    }
  });
});

function withContent(edit: (path: string, raw: string) => string, isProd = false) {
  const edited = Object.fromEntries(Object.entries(files).map(([path, raw]) => [path, edit(path, raw)]));
  vi.mocked(getSection).mockImplementation(buildSiteContent(edited, { isProd }).getSection);
}

it.each([false, true])("removes TBC after publishing security sections (production: %s)", (isProd) => {
  withContent((_, raw) => raw.replace("status: draft", "status: published"), isProd);
  render(<MemoryRouter><SecurityPage /></MemoryRouter>);
  expect(screen.getByText("Is it GDPR compliant?")).toBeInTheDocument();
  expect(screen.getByText("Where is our data stored?")).toBeInTheDocument();
  expect(screen.queryByText("TBC")).not.toBeInTheDocument();
});

it("renders every sector-validation anecdote, not just the first", () => {
  withContent((_, raw) =>
    raw.includes("id: how-it-works.sector-validation\n")
      ? raw.replace("items:\n", "items:\n  - title: Second source\n    body: Second anecdote body.\n")
      : raw);
  render(<MemoryRouter><HowItWorksPage /></MemoryRouter>);
  expect(screen.getByText("Second anecdote body.")).toBeInTheDocument();
  expect(screen.getByText(/One leader of a small local nonprofit/)).toBeInTheDocument();
});

it("skips the question band when every security question is hidden", () => {
  withContent((path, raw) =>
    /security\/(self-hosting|ai-providers|gdpr|data-location|high-risk)\.md$/.test(path)
      ? raw.replace("status: published", "status: draft")
      : raw, true);
  const { container } = render(<MemoryRouter><SecurityPage /></MemoryRouter>);
  expect(Array.from(container.querySelectorAll("section"), (section) => section.id)).toEqual(["intro", "cta"]);
});

it("promotes the who-for card headings to h2 when the who heading is hidden", () => {
  withContent((path, raw) =>
    path.endsWith("how-it-works/who.md") ? raw.replace("status: published", "status: draft") : raw,
    true);
  render(<MemoryRouter><HowItWorksPage /></MemoryRouter>);
  expect(screen.getByRole("heading", { level: 2, name: "If you receive grants" })).toBeInTheDocument();
});

it("promotes the callout headings to h2 when the steps section is hidden", () => {
  withContent((path, raw) =>
    path.endsWith("how-it-works/five-steps.md") ? raw.replace("status: published", "status: draft") : raw,
    true);
  render(<MemoryRouter><HowItWorksPage /></MemoryRouter>);
  expect(screen.getByRole("heading", { level: 2, name: "What we're hearing from the sector" }))
    .toBeInTheDocument();
});

it("does not double up punctuation after a who-for item title", () => {
  withContent((path, raw) =>
    path.endsWith("how-it-works/who-grantees.md")
      ? raw.replace("title: Less time on administration", "title: Why switch?")
      : raw);
  render(<MemoryRouter><HowItWorksPage /></MemoryRouter>);
  expect(screen.getByText("Why switch?").parentElement?.textContent).toMatch(/^Why switch\? Enter/);
});
