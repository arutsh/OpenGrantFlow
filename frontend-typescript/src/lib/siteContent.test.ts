import { buildSiteContent } from "./siteContent";

const PUBLISHED = `---
id: home.hero
page: home
anchor: hero
title: Hero
status: published
---
Hero body.`;

const DRAFT = `---
id: security.data-location
page: security
anchor: data-location
title: Data location
status: draft
---
TBC data location.`;

describe("buildSiteContent", () => {
  it("throws naming the file and the missing field", () => {
    expect(() =>
      buildSiteContent({
        "/a.md": `---
page: home
anchor: hero
title: Hero
status: published
---
Body`,
      }),
    ).toThrow(/\/a\.md: missing required field "id"/);
  });

  it("throws on an invalid page value", () => {
    expect(() =>
      buildSiteContent({
        "/a.md": `---
id: bogus.hero
page: not-a-page
anchor: hero
title: Hero
status: published
---
Body`,
      }),
    ).toThrow(/\/a\.md: invalid "page" value "not-a-page"/);
  });

  it("throws on an invalid status value", () => {
    expect(() =>
      buildSiteContent({
        "/a.md": `---
id: home.hero
page: home
anchor: hero
title: Hero
status: pending
---
Body`,
      }),
    ).toThrow(/\/a\.md: invalid "status" value "pending"/);
  });

  it("throws on an invalid personas value", () => {
    expect(() =>
      buildSiteContent({
        "/a.md": `---
id: home.hero
page: home
anchor: hero
title: Hero
status: published
personas: [grantee, astronaut]
---
Body`,
      }),
    ).toThrow(/\/a\.md: invalid "personas" value/);
  });

  it("throws naming both files on a duplicate id", () => {
    expect(() =>
      buildSiteContent({
        "/a.md": PUBLISHED,
        "/b.md": PUBLISHED.replace("anchor: hero", "anchor: other"),
      }),
    ).toThrow(/duplicate id "home\.hero" in \/a\.md, \/b\.md/);
  });

  it("throws naming both files on a duplicate anchor within the same page", () => {
    expect(() =>
      buildSiteContent({
        "/a.md": PUBLISHED,
        "/b.md": PUBLISHED.replace("id: home.hero", "id: home.hero-2"),
      }),
    ).toThrow(/duplicate anchor "hero" on page "home" in \/a\.md, \/b\.md/);
  });

  it("hides draft sections when isProd is true", () => {
    const { getSection } = buildSiteContent({ "/a.md": DRAFT }, { isProd: true });

    expect(getSection("security.data-location")).toBeNull();
  });

  it("shows draft sections when isProd is false", () => {
    const { getSection } = buildSiteContent({ "/a.md": DRAFT }, { isProd: false });

    const section = getSection("security.data-location");
    expect(section?.status).toBe("draft");
    expect(section?.title).toBe("Data location");
  });

  it("throws on an unknown section id", () => {
    const { getSection } = buildSiteContent({ "/a.md": PUBLISHED });

    expect(() => getSection("home.missing")).toThrow(
      /Unknown site content section "home\.missing"/,
    );
  });

  it("returns published sections unchanged in production", () => {
    const { getSection } = buildSiteContent({ "/a.md": PUBLISHED }, { isProd: true });

    const section = getSection("home.hero");
    expect(section?.status).toBe("published");
    expect(section?.body).toBe("Hero body.");
  });

  it("throws when eyebrow is not a string", () => {
    expect(() =>
      buildSiteContent({
        "/a.md": PUBLISHED.replace("status: published", "status: published\neyebrow: [a, b]"),
      }),
    ).toThrow(/\/a\.md: "eyebrow" must be a string/);
  });

  it("exposes an optional eyebrow", () => {
    const withEyebrow = PUBLISHED.replace("status: published", "status: published\neyebrow: Ours");

    expect(buildSiteContent({ "/a.md": withEyebrow }).getSection("home.hero")?.eyebrow).toBe("Ours");
    expect(buildSiteContent({ "/a.md": PUBLISHED }).getSection("home.hero")?.eyebrow).toBeUndefined();
  });

  it("validates and exposes an optional pill", () => {
    const withPill = PUBLISHED.replace("status: published", "status: published\npill: Available now");

    expect(buildSiteContent({ "/a.md": withPill }).getSection("home.hero")?.pill).toBe("Available now");
    expect(() =>
      buildSiteContent({ "/a.md": PUBLISHED.replace("status: published", "status: published\npill: 3") }),
    ).toThrow(/\/a\.md: "pill" must be a string/);
  });

  it("accepts a link item with no body, but not a bare title", () => {
    const withItem = (item: string) =>
      PUBLISHED.replace("status: published", `status: published\nitems:\n${item}`);

    expect(() =>
      buildSiteContent({ "/a.md": withItem("  - title: Request a demo\n    href: /contact") }),
    ).not.toThrow();
    expect(() => buildSiteContent({ "/a.md": withItem("  - title: Request a demo") })).toThrow(
      /items\[0\] must have a "body", "attribution" or "href"/,
    );
    expect(() => buildSiteContent({ "/a.md": withItem("  - title: Request a demo\n    href: 3") })).toThrow(
      /items\[0\] "href" must be a string/,
    );
  });

  it("parses a file saved with a UTF-8 byte order mark", () => {
    const { getSection } = buildSiteContent({ "/a.md": `\uFEFF${PUBLISHED}` });

    expect(getSection("home.hero")?.title).toBe("Hero");
  });

  it("reports fence and YAML errors alongside other files' validation errors", () => {
    let message = "";
    try {
      buildSiteContent({
        "/no-fence.md": "id: home.hero\nBody",
        "/bad-yaml.md": "---\nid: [unclosed\n---\nBody",
        "/no-id.md": PUBLISHED.replace("id: home.hero\n", ""),
      });
    } catch (error) {
      message = (error as Error).message;
    }

    expect(message).toMatch(/\/no-fence\.md: missing YAML frontmatter fence/);
    expect(message).toMatch(/\/bad-yaml\.md: /);
    expect(message).toMatch(/\/no-id\.md: missing required field "id"/);
  });
});
