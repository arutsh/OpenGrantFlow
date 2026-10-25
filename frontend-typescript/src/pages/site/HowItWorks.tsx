import { getSection, type SiteContentItem } from "@/lib/siteContent";
import { SiteMarkdown } from "@/components/site/SiteMarkdown";
import { SectionVisibility } from "@/components/site/SectionVisibility";
import { PageHero } from "@/components/site/PageHero";
import { SiteSection } from "@/components/site/SiteSection";
import { SectionHead } from "@/components/site/SectionHead";
import { SectionCtaBand } from "@/components/site/CtaBand";
import { Callout } from "@/components/site/Callout";

function TickItem({ item }: { item: SiteContentItem }) {
  const separator = item.title && item.body && !/[.?!:]$/.test(item.title) ? "." : "";
  return (
    <li className="relative pl-7 text-slate-500 before:absolute before:left-0.5 before:top-[0.55em] before:h-[7px] before:w-3 before:-translate-y-1/2 before:-rotate-45 before:border-b-[2.5px] before:border-l-[2.5px] before:border-brand-teal">
      <strong className="font-semibold text-brand-slate">{item.title}</strong>
      {separator}
      {item.body && ` ${item.body}`}
    </li>
  );
}

export default function HowItWorksPage() {
  const intro = getSection("how-it-works.intro");
  const fiveSteps = getSection("how-it-works.five-steps");
  const surveyEvidence = getSection("how-it-works.survey-evidence");
  const roadmap = getSection("how-it-works.roadmap");
  const who = getSection("how-it-works.who");
  const whoGrantees = getSection("how-it-works.who-grantees");
  const whoFunders = getSection("how-it-works.who-funders");
  const sectorValidation = getSection("how-it-works.sector-validation");
  const cta = getSection("how-it-works.cta");

  const quotes = sectorValidation?.items?.filter((item) => item.quote) ?? [];
  const anecdotes = sectorValidation?.items?.filter((item) => !item.quote) ?? [];
  // When an optional parent heading is hidden, its child headings move up a level to keep the outline intact.
  const SubHeading = fiveSteps ? "h3" : "h2";
  const CardHeading = who ? "h3" : "h2";

  return (
    <>
      <title>How it works · Open Grant Flow</title>
      <div className="bg-brand-off-white">
        <SectionVisibility section={intro}>
          {(intro) => <PageHero section={intro} />}
        </SectionVisibility>

        {(fiveSteps || surveyEvidence || roadmap) && (
          <SiteSection alt>
            <SectionVisibility section={fiveSteps}>
              {(fiveSteps) => (
                <div id={fiveSteps.anchor}>
                  <SectionHead eyebrow={fiveSteps.eyebrow} title={fiveSteps.title} />
                  <ol role="list" className="grid max-w-[760px]">
                    {fiveSteps.items?.map((step, index) => (
                      <li
                        key={index}
                        className="grid grid-cols-[auto_1fr] gap-5 border-t border-[#d5dde6] py-[22px] first:border-t-0 first:pt-0"
                      >
                        <span
                          aria-hidden="true"
                          className="grid size-9 place-items-center rounded-full border-[1.5px] border-brand-teal bg-white font-bold text-brand-teal"
                        >
                          {index + 1}
                        </span>
                        <div>
                          <h3 className="mb-1 text-lg font-semibold text-brand-slate">{step.title}</h3>
                          <p className="text-slate-500">{step.body}</p>
                        </div>
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </SectionVisibility>

            <SectionVisibility section={surveyEvidence}>
              {(surveyEvidence) => (
                <Callout
                  id={surveyEvidence.anchor}
                  className="mt-10 [&_em]:mt-1.5 [&_em]:block [&_em]:text-sm [&_em]:not-italic [&_em]:text-slate-500"
                >
                  <SubHeading className="sr-only">{surveyEvidence.title}</SubHeading>
                  <SiteMarkdown>{surveyEvidence.body}</SiteMarkdown>
                </Callout>
              )}
            </SectionVisibility>

            <SectionVisibility section={roadmap}>
              {(roadmap) => (
                <div
                  id={roadmap.anchor}
                  className="mt-7 flex max-w-[78ch] flex-wrap items-baseline gap-x-3.5 gap-y-2 text-slate-500"
                >
                  <SubHeading className="rounded border border-slate-300 bg-white px-2 py-0.5 text-xs font-semibold uppercase tracking-widest text-brand-slate">
                    {roadmap.title}
                  </SubHeading>
                  <SiteMarkdown>{roadmap.body}</SiteMarkdown>
                </div>
              )}
            </SectionVisibility>
          </SiteSection>
        )}

        {(who || whoGrantees || whoFunders) && (
          <SiteSection>
            <SectionVisibility section={who}>
              {(who) => (
                <div id={who.anchor}>
                  <SectionHead eyebrow={who.eyebrow} title={who.title} />
                </div>
              )}
            </SectionVisibility>
            <div className="grid gap-6 md:grid-cols-2">
              {[whoGrantees, whoFunders].map((section, index) => (
                <SectionVisibility key={index} section={section}>
                  {(section) => (
                    <div
                      id={section.anchor}
                      className="grid content-start gap-4 rounded-2xl bg-white p-7 card-shadow-lg"
                    >
                      <CardHeading className="text-[1.4rem] font-bold text-brand-slate">{section.title}</CardHeading>
                      <ul className="grid gap-3">
                        {section.items?.map((item, itemIndex) => (
                          <TickItem key={itemIndex} item={item} />
                        ))}
                      </ul>
                    </div>
                  )}
                </SectionVisibility>
              ))}
            </div>
          </SiteSection>
        )}

        <SectionVisibility section={sectorValidation}>
          {(sectorValidation) => (
            <SiteSection id={sectorValidation.anchor} alt>
              <SectionHead eyebrow={sectorValidation.eyebrow} title={sectorValidation.title} />
              <div className="grid gap-6 md:grid-cols-3">
                {quotes.map((quote, index) => (
                  <blockquote
                    key={index}
                    className="grid content-start gap-3 rounded-2xl bg-white p-6 card-shadow-lg"
                  >
                    <p className="text-lg font-medium leading-snug text-brand-slate">
                      &ldquo;{quote.quote}&rdquo;
                    </p>
                    <cite className="text-sm not-italic text-slate-500">{quote.attribution}</cite>
                  </blockquote>
                ))}
              </div>

              {anecdotes.map((anecdote, index) => (
                <Callout key={index} className="mt-6">
                  <p className="mb-2">{anecdote.body}</p>
                  <p className="text-sm font-semibold text-brand-teal">{anecdote.title}</p>
                </Callout>
              ))}

              <div className="mt-8 max-w-[70ch] text-slate-500 [&_a]:text-brand-navy [&_a]:underline">
                <SiteMarkdown>{sectorValidation.body}</SiteMarkdown>
              </div>
            </SiteSection>
          )}
        </SectionVisibility>

        <SectionCtaBand section={cta} />
      </div>
    </>
  );
}
