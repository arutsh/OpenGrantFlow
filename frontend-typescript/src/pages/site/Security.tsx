import { getSection, type SiteSection } from "@/lib/siteContent";
import { SiteMarkdown } from "@/components/site/SiteMarkdown";
import { SectionVisibility } from "@/components/site/SectionVisibility";
import { PageHero } from "@/components/site/PageHero";
import { SiteSection as SiteSectionWrap } from "@/components/site/SiteSection";
import { SectionCtaBand } from "@/components/site/CtaBand";

function QuestionCard({ section }: { section: SiteSection | null }) {
  return (
    <SectionVisibility section={section}>
      {(section) => (
        <div id={section.anchor} className="grid gap-2.5 rounded-2xl bg-white p-6 card-shadow-lg">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-lg font-semibold leading-snug text-brand-slate">{section.title}</h2>
            {section.pill && section.status === "published" && (
              <span className="whitespace-nowrap rounded-full border border-brand-teal-tint-border bg-brand-teal-tint px-2.5 py-0.5 text-[0.68rem] font-semibold uppercase tracking-wide text-brand-teal">
                {section.pill}
              </span>
            )}
          </div>
          <div className="text-slate-500 [&_a]:text-brand-navy [&_a]:underline">
            <SiteMarkdown>{section.body}</SiteMarkdown>
          </div>
        </div>
      )}
    </SectionVisibility>
  );
}

export default function SecurityPage() {
  const intro = getSection("security.intro");
  const questions = [
    getSection("security.self-hosting"),
    getSection("security.ai-providers"),
    getSection("security.gdpr"),
    getSection("security.data-location"),
    getSection("security.high-risk"),
  ];
  const cta = getSection("security.cta");

  return (
    <>
      <title>Security & data · Open Grant Flow</title>
      <div className="bg-brand-off-white">
        <SectionVisibility section={intro}>
          {(intro) => <PageHero section={intro} />}
        </SectionVisibility>

        {questions.some(Boolean) && (
          <SiteSectionWrap alt>
            <div className="grid max-w-[860px] gap-4">
              {questions.map((section, index) => (
                <QuestionCard key={index} section={section} />
              ))}
            </div>
          </SiteSectionWrap>
        )}

        <SectionCtaBand section={cta} />
      </div>
    </>
  );
}
