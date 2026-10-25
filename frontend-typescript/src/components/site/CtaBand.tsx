import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { SiteSection } from "@/lib/siteContent";
import { SiteMarkdown } from "./SiteMarkdown";
import { SectionVisibility } from "./SectionVisibility";
import { SiteWrap } from "./SiteSection";

const CTA_CLASS =
  "inline-flex min-h-12 items-center rounded-lg bg-white px-6 py-3 font-medium text-brand-navy transition-opacity hover:opacity-90";

export function SectionCtaBand({ section }: { section: SiteSection | null }) {
  return (
    <SectionVisibility section={section}>
      {(section) => (
        <CtaBand
          id={section.anchor}
          title={section.title}
          body={section.body ? <SiteMarkdown>{section.body}</SiteMarkdown> : undefined}
          cta={{
            label: section.items?.[0]?.title ?? "Request a demo",
            to: section.items?.[0]?.href ?? "/contact",
          }}
        />
      )}
    </SectionVisibility>
  );
}

export function CtaBand({ id, title, body, cta }: {
  id?: string;
  title: string;
  body?: ReactNode;
  cta: { label: string; to: string };
}) {
  return (
    <section id={id} className="bg-brand-navy py-16 text-white">
      <SiteWrap className="flex flex-wrap items-center justify-between gap-x-10 gap-y-6">
        <div>
          <h2 className="text-site-h2 max-w-[24ch] text-white">{title}</h2>
          {body && <div className="mt-2.5 max-w-[44ch] text-[#c3d2e2]">{body}</div>}
        </div>
        {cta.to.startsWith("/") || cta.to.startsWith("#") ? (
          <Link to={cta.to} className={CTA_CLASS}>
            {cta.label}
          </Link>
        ) : (
          <a href={cta.to} rel="noopener noreferrer" target="_blank" className={CTA_CLASS}>
            {cta.label}
          </a>
        )}
      </SiteWrap>
    </section>
  );
}
