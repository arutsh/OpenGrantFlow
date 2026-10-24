import { Fragment } from "react";
import { Link } from "react-router-dom";
import type { SiteSection } from "@/lib/siteContent";
import { SiteMarkdown } from "./SiteMarkdown";
import { SiteWrap } from "./SiteSection";
import { SiteAssistantBox } from "./SiteAssistantBox";
import { SectionVisibility } from "./SectionVisibility";

export function AssistantHero({ section, browseInstead, maxQuestionChars }: {
  section: SiteSection;
  browseInstead: SiteSection | null;
  maxQuestionChars: number;
}) {
  return (
    <section id={section.anchor} className="pt-10 pb-12 md:pt-14 md:pb-16">
      <SiteWrap className="grid justify-items-center gap-[22px] text-center">
        <div className="grid max-w-[720px] justify-items-center gap-4">
          <h1 className="text-site-display text-brand-slate">{section.title}</h1>
          <div className="text-site-lede max-w-[56ch] text-brand-slate">
            <SiteMarkdown>{section.body}</SiteMarkdown>
          </div>
        </div>

        <SiteAssistantBox maxQuestionChars={maxQuestionChars} />

        <SectionVisibility section={browseInstead}>
          {(browseInstead) => (
            <p id={browseInstead.anchor} className="text-sm text-slate-500">
              {browseInstead.title}{" "}
              {browseInstead.items?.map((item, index) => (
                <Fragment key={item.title}>
                  {index > 0 && " · "}
                  <Link to={item.href ?? "/"} className="mx-1 text-brand-navy underline hover:opacity-70">
                    {item.title}
                  </Link>
                </Fragment>
              ))}
            </p>
          )}
        </SectionVisibility>
      </SiteWrap>
    </section>
  );
}

// Holds the hero's height while the config loads, so the page doesn't jump.
export function HeroPlaceholder() {
  return (
    <section aria-busy="true" aria-label="Loading" className="pt-10 pb-12 md:pt-14 md:pb-16">
      <SiteWrap className="grid min-h-[520px] content-start justify-items-center gap-4">
        <div className="h-12 w-full max-w-[640px] animate-pulse rounded-lg bg-brand-mist motion-reduce:animate-none" />
        <div className="h-6 w-full max-w-[480px] animate-pulse rounded-lg bg-brand-mist motion-reduce:animate-none" />
      </SiteWrap>
    </section>
  );
}
