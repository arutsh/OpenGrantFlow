import { getSection, type SiteSection } from "@/lib/siteContent";
import { SiteMarkdown } from "@/components/site/SiteMarkdown";
import { SectionVisibility } from "@/components/site/SectionVisibility";

function ProseSection({ section }: { section: SiteSection | null }) {
  return (
    <SectionVisibility section={section}>
      {(section) => (
        <section id={section.anchor} className="max-w-3xl mx-auto px-6 py-10">
          <h2 className="text-2xl font-bold mb-4 text-brand-slate">
            {section.title}
          </h2>
          <div className="text-brand-slate">
            <SiteMarkdown>{section.body}</SiteMarkdown>
          </div>
        </section>
      )}
    </SectionVisibility>
  );
}

export default function SecurityPage() {
  const intro = getSection("security.intro");
  const selfHosting = getSection("security.self-hosting");
  const aiProviders = getSection("security.ai-providers");
  const gdpr = getSection("security.gdpr");
  const dataLocation = getSection("security.data-location");
  const highRisk = getSection("security.high-risk");

  return (
    <>
      <title>Security & data · Open Grant Flow</title>
      <div className="bg-brand-off-white">
        <SectionVisibility section={intro}>
          {(intro) => (
            <section
              id={intro.anchor}
              className="max-w-3xl mx-auto px-6 py-16 text-center"
            >
              <h1 className="text-4xl font-bold mb-6 text-brand-slate">
                {intro.title}
              </h1>
              <div className="text-lg text-brand-slate">
                <SiteMarkdown>{intro.body}</SiteMarkdown>
              </div>
            </section>
          )}
        </SectionVisibility>

        <ProseSection section={selfHosting} />
        <ProseSection section={aiProviders} />
        <ProseSection section={gdpr} />
        <ProseSection section={dataLocation} />
        <ProseSection section={highRisk} />
      </div>
    </>
  );
}
