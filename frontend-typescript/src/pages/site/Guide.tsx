import { Navigate, useParams } from "react-router-dom";
import type { Components } from "react-markdown";
import { getGuideDoc, resolveGuideHref, slugifyHeading } from "@/lib/guideDocs";
import { SiteMarkdown } from "@/components/site/SiteMarkdown";

function headingComponents(raw: string): Components {
  return {
    // Slug from the raw source line so anchors match the ai service's chunk URLs.
    h2: ({ node, children, ...props }) => {
      const start = node?.position?.start.offset;
      const end = node?.position?.end.offset;
      const source = start !== undefined && end !== undefined ? raw.slice(start, end) : "";
      const id = slugifyHeading(source.replace(/^## /, "").trim()) || undefined;
      return (
        <h2 id={id} {...props}>
          {children}
        </h2>
      );
    },
  };
}

export default function GuidePage() {
  const { slug = "" } = useParams();
  const raw = getGuideDoc(slug);
  if (raw === null) return <Navigate to="/" replace />;

  const title = raw.match(/^# (.+)$/m)?.[1].trim() ?? slug;

  return (
    <>
      <title>{`${title} · Open Grant Flow`}</title>
      <main className="max-w-3xl mx-auto px-6 py-16 text-brand-slate space-y-4 [&_h1]:text-3xl [&_h1]:font-bold [&_h2]:text-2xl [&_h2]:font-bold [&_h2]:mt-10 [&_h3]:text-xl [&_h3]:font-semibold [&_h3]:mt-6 [&_ul]:list-disc [&_ul]:pl-6 [&_ol]:list-decimal [&_ol]:pl-6 [&_a]:underline [&_blockquote]:border-l-4 [&_blockquote]:pl-4">
        <SiteMarkdown
          extraComponents={headingComponents(raw)}
          resolveHref={(href) => resolveGuideHref(href, slug)}
        >
          {raw}
        </SiteMarkdown>
      </main>
    </>
  );
}
