import { User } from "lucide-react";
import { getSection, type SiteSection } from "@/lib/siteContent";
import { SiteMarkdown } from "@/components/site/SiteMarkdown";
import { SectionVisibility } from "@/components/site/SectionVisibility";

function CardGrid({ section }: { section: SiteSection }) {
  return (
    <div className="grid sm:grid-cols-2 gap-6">
      {section.items?.map((item, index) => (
        <div key={index} className="bg-white p-6 rounded-2xl card-shadow-lg">
          <h3 className="font-semibold mb-2 text-brand-slate">
            {item.title}
          </h3>
          <p className="text-sm text-slate-500">{item.body}</p>
        </div>
      ))}
    </div>
  );
}

export default function AboutPage() {
  const mission = getSection("about.mission");
  const origin = getSection("about.origin");
  const values = getSection("about.values");
  const setUp = getSection("about.set-up");
  const openCode = getSection("about.open-code");

  return (
    <>
      <title>About · Open Grant Flow</title>
      <div className="bg-brand-off-white">
        <SectionVisibility section={mission}>
          {(mission) => (
            <section id={mission.anchor} className="max-w-3xl mx-auto px-6 py-16 text-center">
              <h1 className="text-4xl font-bold mb-6 text-brand-slate">
                {mission.title}
              </h1>
              <div className="text-lg space-y-4 text-brand-slate">
                <SiteMarkdown>{mission.body}</SiteMarkdown>
              </div>
            </section>
          )}
        </SectionVisibility>

        <SectionVisibility section={origin}>
          {(origin) => (
            <section id={origin.anchor} className="max-w-3xl mx-auto px-6 py-16">
              <h2 className="text-3xl font-bold mb-8 text-brand-slate">
                {origin.title}
              </h2>
              <div className="flex flex-col sm:flex-row gap-8 items-start">
                <div
                  className="shrink-0 h-24 w-24 rounded-full flex items-center justify-center bg-brand-mist"
                >
                  <User size={36} className="text-brand-slate" />
                </div>
                <div className="space-y-4 text-brand-slate">
                  <SiteMarkdown>{origin.body}</SiteMarkdown>
                </div>
              </div>
            </section>
          )}
        </SectionVisibility>

        <SectionVisibility section={values}>
          {(values) => (
            <section
              id={values.anchor}
              className="px-6 py-16 bg-brand-mist"
            >
              <div className="max-w-5xl mx-auto">
                <h2 className="text-3xl font-bold mb-8 text-brand-slate">
                  {values.title}
                </h2>
                <CardGrid section={values} />
              </div>
            </section>
          )}
        </SectionVisibility>

        <SectionVisibility section={setUp}>
          {(setUp) => (
            <section id={setUp.anchor} className="max-w-3xl mx-auto px-6 py-16">
              <h2 className="text-3xl font-bold mb-6 text-brand-slate">
                {setUp.title}
              </h2>
              <div className="text-brand-slate">
                <SiteMarkdown>{setUp.body}</SiteMarkdown>
              </div>
            </section>
          )}
        </SectionVisibility>

        <SectionVisibility section={openCode}>
          {(openCode) => (
            <section id={openCode.anchor} className="max-w-5xl mx-auto px-6 py-16">
              <h2 className="text-3xl font-bold mb-6 text-brand-slate">
                {openCode.title}
              </h2>
              <div className="mb-8 [&_a]:underline text-brand-slate">
                <SiteMarkdown>{openCode.body}</SiteMarkdown>
              </div>
              <CardGrid section={openCode} />
            </section>
          )}
        </SectionVisibility>
      </div>
    </>
  );
}
