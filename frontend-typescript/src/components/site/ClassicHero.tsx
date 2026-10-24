import { Link } from "react-router-dom";
import type { SiteSection } from "@/lib/siteContent";
import { SiteMarkdown } from "./SiteMarkdown";
import { SiteWrap } from "./SiteSection";
import productMockup from "@/assets/logos/opengrantflow-mockup.png";

export function ClassicHero({ section }: { section: SiteSection }) {
  return (
    <section id={section.anchor} className="pt-10 pb-12 md:pt-16 md:pb-[72px]">
      <SiteWrap className="grid justify-items-center gap-[22px] text-center">
        <h1 className="text-site-display max-w-3xl text-brand-slate">{section.title}</h1>
        <div className="text-site-lede grid max-w-[56ch] gap-3 text-brand-slate">
          <SiteMarkdown>{section.body}</SiteMarkdown>
        </div>
        <div className="mt-2 flex flex-wrap justify-center gap-3.5">
          {section.items?.map((item) => (
            <Link
              key={item.title}
              to={item.href ?? "/"}
              className="inline-flex min-h-12 items-center rounded-lg bg-brand-navy px-6 py-3 font-medium text-white transition-opacity hover:opacity-90"
            >
              {item.title}
            </Link>
          ))}
        </div>
        <img
          src={productMockup}
          alt="Open Grant Flow budgets dashboard with the AI budget assistant panel"
          className="mt-10 h-auto w-full max-w-[1040px]"
        />
      </SiteWrap>
    </section>
  );
}
