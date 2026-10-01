import { getSection, type SiteSection } from "@/lib/siteContent";
import { SiteMarkdown } from "@/components/site/SiteMarkdown";
import { SectionVisibility } from "@/components/site/SectionVisibility";

function Subsection({ section }: { section: SiteSection | null }) {
  return (
    <SectionVisibility section={section}>
      {(section) => (
        <div id={section.anchor}>
          <h2 className="font-semibold mb-2 text-brand-slate">
            {section.title}
          </h2>
          <div className="text-brand-slate">
            <SiteMarkdown>{section.body}</SiteMarkdown>
          </div>
        </div>
      )}
    </SectionVisibility>
  );
}

export default function LegalPage() {
  const legalStatus = getSection("legal.privacy-legal-status");
  const infoCollected = getSection("legal.privacy-info-collected");
  const howWeUse = getSection("legal.privacy-how-we-use");
  const selfHosting = getSection("legal.privacy-self-hosting");
  const retention = getSection("legal.privacy-retention");
  const processors = getSection("legal.privacy-processors");
  const privacyContact = getSection("legal.privacy-contact");

  const service = getSection("legal.terms-service");
  const noWarranty = getSection("legal.terms-no-warranty");
  const acceptableUse = getSection("legal.terms-acceptable-use");
  const changes = getSection("legal.terms-changes");
  const termsContact = getSection("legal.terms-contact");

  return (
    <>
      <title>Legal · Open Grant Flow</title>
      <main className="max-w-3xl mx-auto px-6 py-16 space-y-20 text-brand-slate">
        <section id="privacy">
          <h1 className="text-3xl font-bold mb-8">Privacy Policy</h1>
          <div className="space-y-6">
            <Subsection section={legalStatus} />
            <Subsection section={infoCollected} />
            <Subsection section={howWeUse} />
            <Subsection section={selfHosting} />
            <Subsection section={retention} />
            <Subsection section={processors} />
            <Subsection section={privacyContact} />
          </div>
        </section>

        <section id="terms">
          <h1 className="text-3xl font-bold mb-8">Terms of Service</h1>
          <div className="space-y-6">
            <Subsection section={service} />
            <Subsection section={noWarranty} />
            <Subsection section={acceptableUse} />
            <Subsection section={changes} />
            <Subsection section={termsContact} />
          </div>
        </section>
      </main>
    </>
  );
}
