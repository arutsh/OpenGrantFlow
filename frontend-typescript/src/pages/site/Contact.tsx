import { getSection, type SiteSection } from "@/lib/siteContent";
import { SiteMarkdown } from "@/components/site/SiteMarkdown";
import { SectionVisibility } from "@/components/site/SectionVisibility";
import { DemoRequestForm } from "@/components/site/DemoRequestForm";
import { SiteWrap } from "@/components/site/SiteSection";

const EYEBROW = "text-[0.78rem] font-semibold uppercase tracking-[0.12em] text-[#7fd6bc]";
const TICKS =
  "[&_ul]:grid [&_ul]:gap-3 [&_li]:relative [&_li]:pl-7 [&_li]:text-[#e8eff6] [&_li]:before:absolute [&_li]:before:left-0.5 [&_li]:before:top-[0.55em] [&_li]:before:h-[7px] [&_li]:before:w-3 [&_li]:before:-translate-y-1/2 [&_li]:before:-rotate-45 [&_li]:before:border-b-[2.5px] [&_li]:before:border-l-[2.5px] [&_li]:before:border-[#7fd6bc]";
const SUMMARY =
  "flex cursor-pointer list-none justify-between gap-4 font-semibold text-white [&::-webkit-details-marker]:hidden after:text-xl after:font-normal after:leading-none after:content-['+'] group-open:after:content-['−']";

function TickList({ section }: { section: SiteSection | null }) {
  return (
    <SectionVisibility section={section}>
      {(section) => (
        <div id={section.anchor} className="grid content-start gap-3.5">
          <h2 className="text-lg font-semibold text-white">{section.title}</h2>
          <div className={`grid gap-3.5 [&_p]:text-sm [&_p]:text-[#c3d2e2] ${TICKS}`}>
            <SiteMarkdown>{section.body}</SiteMarkdown>
          </div>
        </div>
      )}
    </SectionVisibility>
  );
}

export default function ContactPage() {
  const pilot = getSection("contact.pilot");
  const pilotDetails = getSection("contact.pilot-details");
  const whatYouReceive = getSection("contact.what-you-receive");
  const whatWeAsk = getSection("contact.what-we-ask");
  const demoRequest = getSection("contact.demo-request");
  const faq = getSection("contact.faq");
  const faqTime = getSection("contact.faq-time");

  return (
    <>
      <title>Contact · Open Grant Flow</title>
      <section className="bg-brand-navy py-14 text-white md:py-[72px] [&_[data-tbc]]:bg-amber-400/10">
        <SiteWrap>
          <SectionVisibility section={pilot}>
            {(pilot) => (
              <div id={pilot.anchor} className="grid gap-3.5">
                {pilot.eyebrow && <p className={EYEBROW}>{pilot.eyebrow}</p>}
                <h1 className="text-site-page-title text-white">{pilot.title}</h1>
                <div className="text-site-lede max-w-[65ch] text-[#c3d2e2]">
                  <SiteMarkdown>{pilot.body}</SiteMarkdown>
                </div>
              </div>
            )}
          </SectionVisibility>

          <SectionVisibility section={pilotDetails}>
            {(pilotDetails) => (
              <div id={pilotDetails.anchor} className="mt-10">
                <h2 className="sr-only">{pilotDetails.title}</h2>
                <ol role="list" className="grid gap-5 md:grid-cols-3">
                  {pilotDetails.items?.map((item, index) => (
                    <li key={index} className="grid content-start gap-2 rounded-2xl bg-white p-6 card-shadow-lg">
                      <p className="text-site-eyebrow">Month {index + 1}</p>
                      <h3 className="text-lg font-semibold text-brand-slate">{item.title}</h3>
                      <p className="text-slate-500">{item.body}</p>
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </SectionVisibility>

          {(whatYouReceive || whatWeAsk) && (
            <div className="mt-12 grid gap-9 md:grid-cols-2 md:gap-12">
              <TickList section={whatYouReceive} />
              <TickList section={whatWeAsk} />
            </div>
          )}

          <div className="mt-14 grid items-start gap-9 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:gap-14">
            <SectionVisibility section={demoRequest}>
              {(demoRequest) => (
                <div id={demoRequest.anchor} className="grid gap-[18px]">
                  {demoRequest.eyebrow && <p className={EYEBROW}>{demoRequest.eyebrow}</p>}
                  <h2 className="text-site-h2 text-white">{demoRequest.title}</h2>
                  <div className={`grid gap-[18px] [&_p]:text-[#c3d2e2] ${TICKS}`}>
                    <SiteMarkdown>{demoRequest.body}</SiteMarkdown>
                  </div>
                </div>
              )}
            </SectionVisibility>
            <DemoRequestForm heading="Request your demo" />
          </div>

          {(faq || faqTime) && (
            <div className="mt-12 max-w-[880px] border-b border-[#2c5277]">
              <SectionVisibility section={faq}>
                {(faq) => (
                  <div id={faq.anchor}>
                    <h2 className="sr-only">{faq.title}</h2>
                    {faq.items?.map((item, index) => (
                      <details key={index} className="group border-t border-[#2c5277] py-3.5">
                        <summary className={SUMMARY}>{item.title}</summary>
                        <div className="mt-2.5 text-[#c3d2e2] [&_a]:text-white [&_a]:underline">
                          <SiteMarkdown>{item.body ?? ""}</SiteMarkdown>
                        </div>
                      </details>
                    ))}
                  </div>
                )}
              </SectionVisibility>

              <SectionVisibility section={faqTime}>
                {(faqTime) => (
                  <details id={faqTime.anchor} className="group border-t border-[#2c5277] py-3.5">
                    <summary className={SUMMARY}>{faqTime.title}</summary>
                    <div className="mt-2.5 text-[#c3d2e2]">
                      <SiteMarkdown>{faqTime.body}</SiteMarkdown>
                    </div>
                  </details>
                )}
              </SectionVisibility>
            </div>
          )}
        </SiteWrap>
      </section>
    </>
  );
}
