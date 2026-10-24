import { assistantSuggestions, buildAssistantSuggestions } from "./assistantSuggestions";

const PATH = "/suggested-questions.md";

function fileWith(sets: Record<string, string[] | undefined>) {
  const yaml = Object.entries(sets)
    .filter(([, questions]) => questions !== undefined)
    .map(([set, questions]) =>
      questions!.length === 0
        ? `${set}: []`
        : `${set}:\n${questions!.map((q) => `  - ${q}`).join("\n")}`,
    )
    .join("\n");
  return `---\n${yaml}\n---\n`;
}

const VALID = {
  default: ["Q1?", "Q2?"],
  grantee: ["G1?"],
  funder: ["F1?", "F2?", "F3?", "F4?"],
  technical: ["T1?"],
};

describe("buildAssistantSuggestions", () => {
  it("returns every set from a valid file", () => {
    expect(buildAssistantSuggestions(fileWith(VALID), PATH)).toEqual(VALID);
  });

  it("fails naming the file and a missing set", () => {
    expect(() =>
      buildAssistantSuggestions(fileWith({ ...VALID, funder: undefined }), PATH),
    ).toThrow(/\/suggested-questions\.md: missing set "funder"/);
  });

  it("fails naming the file and an empty set", () => {
    expect(() => buildAssistantSuggestions(fileWith({ ...VALID, grantee: [] }), PATH)).toThrow(
      /\/suggested-questions\.md: set "grantee" must hold 1–4 questions, has 0/,
    );
  });

  it("fails naming the file and a five-question set", () => {
    const five = ["F1?", "F2?", "F3?", "F4?", "F5?"];
    expect(() => buildAssistantSuggestions(fileWith({ ...VALID, funder: five }), PATH)).toThrow(
      /\/suggested-questions\.md: set "funder" must hold 1–4 questions, has 5/,
    );
  });

  it("fails naming the file and a set that repeats a question", () => {
    expect(() =>
      buildAssistantSuggestions(fileWith({ ...VALID, default: ["Q1?", "Q1?"] }), PATH),
    ).toThrow(/\/suggested-questions\.md: set "default" repeats a question/);
  });

  it("loads the shipped suggestions file", () => {
    expect(Object.keys(assistantSuggestions).sort()).toEqual(
      ["default", "funder", "grantee", "technical"],
    );
  });
});
