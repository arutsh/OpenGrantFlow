import { getSection } from "@/lib/siteContent";
import { SiteMarkdown } from "@/components/site/SiteMarkdown";
import { SectionVisibility } from "@/components/site/SectionVisibility";

export default function HowItWorksPage() {
  const intro = getSection("how-it-works.intro");
  const fiveSteps = getSection("how-it-works.five-steps");
  const surveyEvidence = getSection("how-it-works.survey-evidence");
  const roadmap = getSection("how-it-works.roadmap");
  const whoGrantees = getSection("how-it-works.who-grantees");
  const whoFunders = getSection("how-it-works.who-funders");
  const sectorValidation = getSection("how-it-works.sector-validation");

  const quotes = sectorValidation?.items?.filter((item) => item.quote) ?? [];
  const anecdotes = sectorValidation?.items?.filter((item) => !item.quote) ?? [];

  return (
    <>
      <title>How it works · Open Grant Flow</title>
      <div className="bg-brand-off-white">
        <SectionVisibility section={intro}>
          {(intro) => (
            <section id={intro.anchor} className="max-w-3xl mx-auto px-6 py-16 text-center">
              <h1 className="text-4xl font-bold mb-6 text-brand-slate">
                {intro.title}
              </h1>
              <div className="text-lg text-brand-slate">
                <SiteMarkdown>{intro.body}</SiteMarkdown>
              </div>
            </section>
          )}
        </SectionVisibility>

        <SectionVisibility section={fiveSteps}>
          {(fiveSteps) => (
            <section id={fiveSteps.anchor} className="max-w-5xl mx-auto px-6 py-16">
              <h2
                className="text-3xl font-bold mb-8 text-center text-brand-slate"
              >
                {fiveSteps.title}
              </h2>
              <ol className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
                {fiveSteps.items?.map((step, index) => (
                  <li
                    key={index}
                    className="bg-white rounded-2xl card-shadow-lg p-6"
                  >
                    <p
                      className="text-xs font-semibold uppercase tracking-widest mb-2 text-brand-gold"
                    >
                      Step {index + 1}
                    </p>
                    <h3 className="font-semibold mb-2 text-brand-slate">
                      {step.title}
                    </h3>
                    <p className="text-sm text-slate-500">{step.body}</p>
                  </li>
                ))}
              </ol>
            </section>
          )}
        </SectionVisibility>

        <SectionVisibility section={sectorValidation}>
          {(sectorValidation) => (
            <section
              id={sectorValidation.anchor}
              className="px-6 py-16 bg-brand-mist"
            >
              <div className="max-w-5xl mx-auto">
                <h2
                  className="text-xs font-semibold tracking-widest uppercase mb-6 text-brand-teal"
                >
                  {sectorValidation.title}
                </h2>

                <div className="grid sm:grid-cols-3 gap-5">
                  {quotes.map((quote, index) => (
                    <div
                      key={index}
                      className="bg-white rounded-2xl card-shadow-lg p-6 flex flex-col gap-4"
                    >
                      <p className="italic flex-grow text-brand-slate">
                        &ldquo;{quote.quote}&rdquo;
                      </p>
                      <p className="text-sm font-semibold text-brand-teal">
                        {quote.attribution}
                      </p>
                    </div>
                  ))}
                </div>

                {anecdotes.map((anecdote, index) => (
                  <div
                    key={index}
                    className="mt-5 rounded-2xl p-6 bg-brand-teal-tint border border-brand-teal-tint-border"
                  >
                    <p className="mb-3 text-brand-slate">
                      {anecdote.body}
                    </p>
                    <p className="text-sm font-semibold text-brand-teal">
                      {anecdote.title}
                    </p>
                  </div>
                ))}

                <p
                  className="mt-10 text-center text-xl font-bold text-brand-teal"
                >
                  {sectorValidation.body}
                </p>
              </div>
            </section>
          )}
        </SectionVisibility>

        <SectionVisibility section={surveyEvidence}>
          {(surveyEvidence) => (
            <section id={surveyEvidence.anchor} className="max-w-3xl mx-auto px-6 py-16">
              <h2 className="text-3xl font-bold mb-6 text-brand-slate">
                {surveyEvidence.title}
              </h2>
              <div className="text-brand-slate">
                <SiteMarkdown>{surveyEvidence.body}</SiteMarkdown>
              </div>
            </section>
          )}
        </SectionVisibility>

        {(whoGrantees || whoFunders) && (
          <section className="px-6 py-16 bg-brand-mist">
            <div className="max-w-5xl mx-auto text-center">
              <h2
                className="text-3xl font-bold mb-12 text-brand-slate"
              >
                Who is this for?
              </h2>
              <div className="grid sm:grid-cols-2 gap-8">
                {[whoGrantees, whoFunders].map((section, index) => (
                  <SectionVisibility key={index} section={section}>
                    {(section) => (
                      <div id={section.anchor} className="text-left">
                        <h3
                          className="font-semibold mb-4 text-center text-brand-slate"
                        >
                          {section.title}
                        </h3>
                        <div className="space-y-4">
                          {section.items?.map((item, itemIndex) => (
                            <div
                              key={itemIndex}
                              className="bg-white p-6 rounded-2xl card-shadow-lg"
                            >
                              <h4
                                className="font-semibold mb-2 text-brand-slate"
                              >
                                {item.title}
                              </h4>
                              <p className="text-sm text-slate-500">{item.body}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </SectionVisibility>
                ))}
              </div>
            </div>
          </section>
        )}

        <SectionVisibility section={roadmap}>
          {(roadmap) => (
            <section id={roadmap.anchor} className="max-w-3xl mx-auto px-6 py-16">
              <h2 className="text-3xl font-bold mb-6 text-brand-slate">
                {roadmap.title}
              </h2>
              <div className="text-brand-slate">
                <SiteMarkdown>{roadmap.body}</SiteMarkdown>
              </div>
            </section>
          )}
        </SectionVisibility>
      </div>
    </>
  );
}
