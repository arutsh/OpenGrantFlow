import type { SiteSection } from "@/lib/siteContent";
import { SiteMarkdown } from "./SiteMarkdown";
import { SectionHead } from "./SectionHead";
import { SiteWrap } from "./SiteSection";

export function PageHero({ section }: { section: SiteSection }) {
  return (
    <section id={section.anchor} className="pt-16 pb-10">
      <SiteWrap>
        <SectionHead
          as="h1"
          eyebrow={section.eyebrow}
          title={section.title}
          intro={section.body ? <SiteMarkdown>{section.body}</SiteMarkdown> : undefined}
        />
      </SiteWrap>
    </section>
  );
}
