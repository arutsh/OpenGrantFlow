const GUIDE_FILES = import.meta.glob(
  ["../../../docs/user-guide/*.md", "!../../../docs/user-guide/README.md"],
  { eager: true, query: "?raw", import: "default" },
) as Record<string, string>;

const PRODUCT_FILE = import.meta.glob("../../../docs/PRODUCT.md", {
  eager: true,
  query: "?raw",
  import: "default",
}) as Record<string, string>;

function slugFromPath(path: string): string {
  return path.split("/").pop()!.replace(/\.md$/, "").toLowerCase();
}

const GUIDE_DOCS = new Map<string, string>([
  ...Object.entries(GUIDE_FILES).map(([path, raw]) => [slugFromPath(path), raw] as const),
  ...Object.values(PRODUCT_FILE).map((raw) => ["product", raw] as const),
]);

export function getGuideDoc(slug: string): string | null {
  return GUIDE_DOCS.get(slug) ?? null;
}

const REPO_URL = "https://github.com/arutsh/OpenGrantFlow";

const SLUG_BY_REPO_PATH = new Map<string, string>([
  ...Object.keys(GUIDE_FILES).map((path) => [path.replace(/^(\.\.\/)+/, ""), slugFromPath(path)] as const),
  ["docs/PRODUCT.md", "product"],
]);

function docDir(slug: string): string {
  return slug === "product" ? "docs" : "docs/user-guide";
}

// Doc links are written for GitHub; route ones to published guides, the rest to the repo.
export function resolveGuideHref(href: string, slug: string): string {
  if (/^([a-z][a-z0-9+.-]*:|#|\/)/i.test(href)) return href;
  const [path, hash] = href.split("#");
  const repoPath = new URL(path, `https://repo/${docDir(slug)}/`).pathname.slice(1);
  const fragment = hash ? `#${hash}` : "";
  const guideSlug = SLUG_BY_REPO_PATH.get(repoPath);
  if (guideSlug) return `/guides/${guideSlug}${fragment}`;
  if (repoPath.startsWith("docs/")) return `${REPO_URL}/blob/main/${repoPath}${fragment}`;
  return `${REPO_URL}/${repoPath}${fragment}`;
}

// Must stay in sync with _slugify in services/ai/app/services/guide_doc_ingestion.py.
export function slugifyHeading(text: string): string {
  const slug = text.toLowerCase().replace(/[^a-z0-9\s-]/g, "");
  return slug
    .trim()
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-+|-+$/g, "");
}
