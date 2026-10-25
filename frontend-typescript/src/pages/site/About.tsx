import type { ReactNode } from "react";
import { getSection } from "@/lib/siteContent";
import { SiteMarkdown } from "@/components/site/SiteMarkdown";
import { SectionVisibility } from "@/components/site/SectionVisibility";
import { PageHero } from "@/components/site/PageHero";
import { SiteSection } from "@/components/site/SiteSection";
import { SectionHead } from "@/components/site/SectionHead";
import { SectionCtaBand } from "@/components/site/CtaBand";

function Story({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="grid items-start gap-6 md:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)] md:gap-14">
      <h2 className="text-site-h2 text-brand-slate md:sticky md:top-24">{title}</h2>
      {children}
    </div>
  );
}

export default function AboutPage() {
  const intro = getSection("about.intro");
  const origin = getSection("about.origin");
  const mission = getSection("about.mission");
  const values = getSection("about.values");
  const model = getSection("about.model");
  const setUp = getSection("about.set-up");
  const openCode = getSection("about.open-code");
  const cta = getSection("about.cta");

  const setUpNote = (
    <SectionVisibility section={setUp}>
      {(setUp) => (
        <div id={setUp.anchor} className="text-brand-slate">
          {!model && <h2 className="text-site-h2 mb-3">{setUp.title}</h2>}
          <SiteMarkdown>{setUp.body}</SiteMarkdown>
        </div>
      )}
    </SectionVisibility>
  );

  return (
    <>
      <title>About · Open Grant Flow</title>
      <div className="bg-brand-off-white">
        <SectionVisibility section={intro}>
          {(intro) => <PageHero section={intro} />}
        </SectionVisibility>

        <SectionVisibility section={origin}>
          {(origin) => (
            <SiteSection id={origin.anchor}>
              <Story title={origin.title}>
                <div className="grid gap-5 text-[1.12rem] text-brand-slate">
                  <SiteMarkdown>{origin.body}</SiteMarkdown>
                </div>
              </Story>
            </SiteSection>
          )}
        </SectionVisibility>

        <SectionVisibility section={mission}>
          {(mission) => (
            <SiteSection id={mission.anchor} alt>
              <Story title={mission.title}>
                <div className="grid gap-5 text-[1.12rem] text-brand-slate [&_blockquote]:max-w-[34ch] [&_blockquote]:border-l-[3px] [&_blockquote]:border-brand-teal [&_blockquote]:pl-5 [&_blockquote]:text-[1.45rem] [&_blockquote]:font-semibold [&_blockquote]:leading-snug">
                  <SiteMarkdown>{mission.body}</SiteMarkdown>
                </div>
              </Story>
            </SiteSection>
          )}
        </SectionVisibility>

        <SectionVisibility section={values}>
          {(values) => (
            <SiteSection id={values.anchor}>
              <Story title={values.title}>
                <ul role="list" className="grid gap-4">
                  {values.items?.map((item, index) => (
                    <li key={index} className="grid gap-2.5 rounded-2xl bg-white p-6 card-shadow-lg">
                      <h3 className="text-xl font-semibold leading-snug text-brand-slate">{item.title}</h3>
                      <p className="text-slate-500">{item.body}</p>
                    </li>
                  ))}
                </ul>
              </Story>
            </SiteSection>
          )}
        </SectionVisibility>

        {(model || setUp || openCode) && (
          <SiteSection alt>
            {model ? (
              <SectionVisibility section={model}>
                {(model) => (
                  <div id={model.anchor}>
                    <SectionHead eyebrow={model.eyebrow} title={model.title} intro={setUp && setUpNote} />
                    <ul role="list" className="grid gap-6 md:grid-cols-3">
                      {model.items?.map((item, index) => (
                        <li key={index} className="grid content-start gap-2 rounded-2xl bg-white p-6 card-shadow-lg">
                          <h3 className="text-lg font-semibold text-brand-slate">{item.title}</h3>
                          <p className="text-slate-500">{item.body}</p>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </SectionVisibility>
            ) : (
              setUpNote
            )}

            <SectionVisibility section={openCode}>
              {(openCode) => (
                <div id={openCode.anchor} className="mt-7 text-sm text-slate-500 [&_a]:text-brand-navy [&_a]:underline">
                  <h2 className="sr-only">{openCode.title}</h2>
                  <SiteMarkdown>{openCode.body}</SiteMarkdown>
                </div>
              )}
            </SectionVisibility>
          </SiteSection>
        )}

        <SectionCtaBand section={cta} />
      </div>
    </>
  );
}
