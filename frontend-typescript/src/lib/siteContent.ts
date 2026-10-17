import { parse as parseYaml } from "yaml";

export type SitePage =
  | "home"
  | "how-it-works"
  | "security"
  | "about"
  | "contact"
  | "legal";

export type SitePersona = "grantee" | "funder" | "technical";

export type SiteSectionStatus = "published" | "draft";

export interface SiteContentItem {
  title?: string;
  quote?: string;
  body?: string;
  attribution?: string;
  href?: string;
  [key: string]: unknown;
}

export interface SiteSection {
  id: string;
  page: SitePage;
  anchor: string;
  title: string;
  status: SiteSectionStatus;
  personas?: SitePersona[];
  items?: SiteContentItem[];
  body: string;
}

const PAGES: SitePage[] = [
  "home",
  "how-it-works",
  "security",
  "about",
  "contact",
  "legal",
];
const STATUSES: SiteSectionStatus[] = ["published", "draft"];
const PERSONAS: SitePersona[] = ["grantee", "funder", "technical"];

interface ParsedFile {
  path: string;
  frontmatter: Record<string, unknown>;
  body: string;
}

function splitFrontmatter(raw: string): { frontmatter: unknown; body: string } {
  const withoutBom = raw.replace(/^\uFEFF/, "");
  const match = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/.exec(withoutBom);
  if (!match) {
    throw new Error("missing YAML frontmatter fence");
  }
  const [, frontmatterYaml, body] = match;
  return { frontmatter: parseYaml(frontmatterYaml), body: body.trim() };
}

function validateItems(
  items: unknown,
  path: string,
  errors: string[],
): void {
  if (!Array.isArray(items)) {
    errors.push(`${path}: "items" must be a list`);
    return;
  }
  items.forEach((item, index) => {
    if (typeof item !== "object" || item === null) {
      errors.push(`${path}: items[${index}] must be an object`);
      return;
    }
    const candidate = item as SiteContentItem;
    if (!candidate.title && !candidate.quote) {
      errors.push(`${path}: items[${index}] must have a "title" or "quote"`);
    }
    if (!candidate.body && !candidate.attribution) {
      errors.push(`${path}: items[${index}] must have a "body" or "attribution"`);
    }
  });
}

function validateFrontmatter(
  frontmatter: Record<string, unknown>,
  path: string,
  errors: string[],
): void {
  for (const field of ["id", "page", "anchor", "title", "status"] as const) {
    if (!frontmatter[field]) {
      errors.push(`${path}: missing required field "${field}"`);
    }
  }
  if (
    frontmatter.page !== undefined &&
    !PAGES.includes(frontmatter.page as SitePage)
  ) {
    errors.push(`${path}: invalid "page" value "${String(frontmatter.page)}"`);
  }
  if (
    frontmatter.status !== undefined &&
    !STATUSES.includes(frontmatter.status as SiteSectionStatus)
  ) {
    errors.push(`${path}: invalid "status" value "${String(frontmatter.status)}"`);
  }
  if (frontmatter.personas !== undefined) {
    const personas = frontmatter.personas;
    const valid =
      Array.isArray(personas) &&
      personas.every((persona) => PERSONAS.includes(persona as SitePersona));
    if (!valid) {
      errors.push(
        `${path}: invalid "personas" value "${JSON.stringify(frontmatter.personas)}"`,
      );
    }
  }
  if (frontmatter.items !== undefined) {
    validateItems(frontmatter.items, path, errors);
  }
}

function findDuplicates(parsed: ParsedFile[], errors: string[]): void {
  const idToPaths = new Map<string, string[]>();
  const anchorToPaths = new Map<string, string[]>();

  for (const file of parsed) {
    const id = file.frontmatter.id as string | undefined;
    const page = file.frontmatter.page as string | undefined;
    const anchor = file.frontmatter.anchor as string | undefined;
    if (id) {
      idToPaths.set(id, [...(idToPaths.get(id) ?? []), file.path]);
    }
    if (page && anchor) {
      const key = `${page}::${anchor}`;
      anchorToPaths.set(key, [...(anchorToPaths.get(key) ?? []), file.path]);
    }
  }

  for (const [id, paths] of idToPaths) {
    if (paths.length > 1) {
      errors.push(`duplicate id "${id}" in ${paths.join(", ")}`);
    }
  }
  for (const [key, paths] of anchorToPaths) {
    if (paths.length > 1) {
      const [page, anchor] = key.split("::");
      errors.push(`duplicate anchor "${anchor}" on page "${page}" in ${paths.join(", ")}`);
    }
  }
}

export function buildSiteContent(
  rawFiles: Record<string, string>,
  options: { isProd?: boolean } = {},
) {
  const errors: string[] = [];
  const parsed: ParsedFile[] = [];

  for (const [path, raw] of Object.entries(rawFiles)) {
    let frontmatter: unknown;
    let body: string;
    try {
      ({ frontmatter, body } = splitFrontmatter(raw));
    } catch (error) {
      errors.push(`${path}: ${error instanceof Error ? error.message : String(error)}`);
      continue;
    }
    if (typeof frontmatter !== "object" || frontmatter === null) {
      errors.push(`${path}: frontmatter must be a YAML mapping`);
      continue;
    }
    parsed.push({ path, frontmatter: frontmatter as Record<string, unknown>, body });
  }

  for (const file of parsed) {
    validateFrontmatter(file.frontmatter, file.path, errors);
  }
  findDuplicates(parsed, errors);

  if (errors.length > 0) {
    throw new Error(`Site content validation failed:\n${errors.join("\n")}`);
  }

  const sections = new Map<string, SiteSection>();
  for (const file of parsed) {
    const fm = file.frontmatter;
    sections.set(fm.id as string, {
      id: fm.id as string,
      page: fm.page as SitePage,
      anchor: fm.anchor as string,
      title: fm.title as string,
      status: fm.status as SiteSectionStatus,
      personas: fm.personas as SitePersona[] | undefined,
      items: fm.items as SiteContentItem[] | undefined,
      body: file.body,
    });
  }

  function getSection(id: string): SiteSection | null {
    const section = sections.get(id);
    if (!section) {
      throw new Error(`Unknown site content section "${id}"`);
    }
    const isProd = options.isProd ?? import.meta.env.PROD;
    if (section.status === "draft" && isProd) {
      return null;
    }
    return section;
  }

  return { getSection, sections };
}

const RAW_FILES = import.meta.glob(
  ["../content/site/**/*.md", "!../content/site/README.md"],
  { eager: true, query: "?raw", import: "default" },
) as Record<string, string>;

const siteContent = buildSiteContent(RAW_FILES);

export const getSection = siteContent.getSection;
