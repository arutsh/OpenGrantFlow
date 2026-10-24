import type { SiteAssistantPersona } from "@/api/siteAssistantApi";
import { splitFrontmatter } from "./siteContent";
import rawSuggestions from "../content/assistant/suggested-questions.md?raw";

export type SuggestionSet = "default" | SiteAssistantPersona;

export type AssistantSuggestions = Record<SuggestionSet, string[]>;

const SETS: SuggestionSet[] = ["default", "grantee", "funder", "technical"];
const MAX_PER_SET = 4;

export function buildAssistantSuggestions(raw: string, path: string): AssistantSuggestions {
  let frontmatter: unknown;
  try {
    ({ frontmatter } = splitFrontmatter(raw));
  } catch (error) {
    throw new Error(`${path}: ${error instanceof Error ? error.message : String(error)}`);
  }
  const data = (typeof frontmatter === "object" && frontmatter !== null
    ? frontmatter
    : {}) as Record<string, unknown>;

  const errors: string[] = [];
  for (const set of SETS) {
    const questions = data[set];
    if (questions === undefined) {
      errors.push(`${path}: missing set "${set}"`);
    } else if (!Array.isArray(questions) || questions.some((q) => typeof q !== "string" || !q.trim())) {
      errors.push(`${path}: set "${set}" must be a list of non-empty strings`);
    } else if (questions.length === 0 || questions.length > MAX_PER_SET) {
      errors.push(`${path}: set "${set}" must hold 1–${MAX_PER_SET} questions, has ${questions.length}`);
    } else if (new Set(questions).size !== questions.length) {
      errors.push(`${path}: set "${set}" repeats a question`);
    }
  }
  if (errors.length > 0) {
    throw new Error(`Assistant suggestions validation failed:\n${errors.join("\n")}`);
  }
  return Object.fromEntries(SETS.map((set) => [set, data[set]])) as AssistantSuggestions;
}

export const assistantSuggestions = buildAssistantSuggestions(
  rawSuggestions,
  "content/assistant/suggested-questions.md",
);
