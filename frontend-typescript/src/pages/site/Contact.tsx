import { getSection, type SiteSection } from "@/lib/siteContent";
import { SiteMarkdown } from "@/components/site/SiteMarkdown";
import { SectionVisibility } from "@/components/site/SectionVisibility";
import { DemoRequestForm } from "@/components/site/DemoRequestForm";

function ItemList({ section }: { section: SiteSection | null }) {
  return (
    <SectionVisibility section={section}>
      {(section) => (
        <div id={section.anchor} className="bg-white p-6 rounded-2xl card-shadow-lg">
          <h3 className="font-semibold mb-4 text-brand-slate">
            {section.title}
          </h3>
          <ul className="space-y-3">
            {section.items?.map((item, index) => (
              <li key={index}>
                <p className="font-medium text-brand-slate">
                  {item.title}
                </p>
                <p className="text-sm text-slate-500">{item.body}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </SectionVisibility>
  );
}

export default function ContactPage() {
  const demoRequest = getSection("contact.demo-request");
  const pilot = getSection("contact.pilot");
  const pilotDetails = getSection("contact.pilot-details");
  const whatYouReceive = getSection("contact.what-you-receive");
  const whatWeAsk = getSection("contact.what-we-ask");
  const faq = getSection("contact.faq");
  const faqTime = getSection("contact.faq-time");

  return (
    <>
      <title>Contact · Open Grant Flow</title>
      <div className="bg-brand-off-white">
        <SectionVisibility section={demoRequest}>
          {(demoRequest) => (
            <section id={demoRequest.anchor} className="max-w-2xl mx-auto px-6 py-16">
              <h1 className="text-4xl font-bold mb-4 text-brand-slate">
                {demoRequest.title}
              </h1>
              <div className="text-lg mb-8 text-brand-slate">
                <SiteMarkdown>{demoRequest.body}</SiteMarkdown>
              </div>
              <DemoRequestForm />
            </section>
          )}
        </SectionVisibility>

        {(pilot || pilotDetails || whatYouReceive || whatWeAsk) && (
          <div className="px-6 py-16 bg-brand-mist">
            <div className="max-w-3xl mx-auto space-y-8">
              <SectionVisibility section={pilot}>
                {(pilot) => (
                  <section id={pilot.anchor}>
                    <h2 className="text-3xl font-bold mb-6 text-brand-slate">
                      {pilot.title}
                    </h2>
                    <div className="space-y-4 text-brand-slate">
                      <SiteMarkdown>{pilot.body}</SiteMarkdown>
                    </div>
                  </section>
                )}
              </SectionVisibility>

              <SectionVisibility section={pilotDetails}>
                {(pilotDetails) => (
                  <section id={pilotDetails.anchor}>
                    <h3 className="font-semibold mb-2 text-brand-slate">
                      {pilotDetails.title}
                    </h3>
                    <div className="text-brand-slate">
                      <SiteMarkdown>{pilotDetails.body}</SiteMarkdown>
                    </div>
                  </section>
                )}
              </SectionVisibility>

              <div className="grid sm:grid-cols-2 gap-6">
                <ItemList section={whatYouReceive} />
                <ItemList section={whatWeAsk} />
              </div>
            </div>
          </div>
        )}

        {(faq || faqTime) && (
          <div className="max-w-3xl mx-auto px-6 py-16 space-y-6">
            <SectionVisibility section={faq}>
              {(faq) => (
                <section id={faq.anchor}>
                  <h2 className="text-3xl font-bold mb-6 text-brand-slate">
                    {faq.title}
                  </h2>
                  <dl className="space-y-5">
                    {faq.items?.map((item, index) => (
                      <div key={index}>
                        <dt className="font-semibold text-brand-slate">
                          {item.title}
                        </dt>
                        <dd className="text-slate-600">{item.body}</dd>
                      </div>
                    ))}
                  </dl>
                </section>
              )}
            </SectionVisibility>

            <SectionVisibility section={faqTime}>
              {(faqTime) => (
                <section id={faqTime.anchor}>
                  <h3 className="font-semibold text-brand-slate">
                    {faqTime.title}
                  </h3>
                  <div className="text-slate-600">
                    <SiteMarkdown>{faqTime.body}</SiteMarkdown>
                  </div>
                </section>
              )}
            </SectionVisibility>
          </div>
        )}
      </div>
    </>
  );
}
