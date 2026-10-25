import { buildPrivacyNotice, privacyNotice } from "./privacyNotice";

const PATH = "/privacy-banner.md";

function fileWith(frontmatter: string, body = "Questions are kept for 90 days.") {
  return `---\n${frontmatter}\n---\n\n${body}\n`;
}

describe("buildPrivacyNotice", () => {
  it("returns status, version and body from a valid file", () => {
    expect(buildPrivacyNotice(fileWith("status: draft\nversion: 2026-10-1"), PATH)).toEqual({
      status: "draft",
      version: "2026-10-1",
      body: "Questions are kept for 90 days.",
    });
  });

  it("fails naming the file and a missing status", () => {
    expect(() => buildPrivacyNotice(fileWith("version: 2026-10-1"), PATH)).toThrow(
      /\/privacy-banner\.md: missing required field "status"/,
    );
  });

  it("fails naming the file and an unknown status", () => {
    expect(() =>
      buildPrivacyNotice(fileWith("status: live\nversion: 2026-10-1"), PATH),
    ).toThrow(/\/privacy-banner\.md: invalid "status" value "live"/);
  });

  it("fails naming the file and a missing version", () => {
    expect(() => buildPrivacyNotice(fileWith("status: draft"), PATH)).toThrow(
      /\/privacy-banner\.md: missing required field "version"/,
    );
  });

  it("fails naming the file and a non-string version", () => {
    expect(() => buildPrivacyNotice(fileWith("status: draft\nversion: 3"), PATH)).toThrow(
      /\/privacy-banner\.md: "version" must be a non-empty string/,
    );
  });

  it("fails naming the file and an empty body", () => {
    expect(() =>
      buildPrivacyNotice(fileWith("status: draft\nversion: 2026-10-1", "  "), PATH),
    ).toThrow(/\/privacy-banner\.md: body must not be empty/);
  });

  it("loads the shipped notice as a draft linking to the privacy policy", () => {
    expect(privacyNotice.status).toBe("draft");
    expect(privacyNotice.version).toBe("2026-10-1");
    expect(privacyNotice.body).toContain("(/legal#privacy)");
  });
});
