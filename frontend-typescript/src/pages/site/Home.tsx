import { useEffect } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { getSection } from "@/lib/siteContent";
import { SiteMarkdown } from "@/components/site/SiteMarkdown";
import { SectionVisibility } from "@/components/site/SectionVisibility";
import { ClassicHero } from "@/components/site/ClassicHero";
import { SiteSection } from "@/components/site/SiteSection";
import { SectionHead } from "@/components/site/SectionHead";
import { CtaBand } from "@/components/site/CtaBand";
import { SiteAssistantBox } from "@/components/site/SiteAssistantBox";
import { useSiteAssistantConfig } from "@/api/siteAssistantApi";

const LEGACY_HASH_REDIRECTS: Record<string, string> = {
  "#contact": "/contact",
  "#about": "/about",
  "#vision": "/about",
  "#platform": "/how-it-works",
  "#problem": "/how-it-works",
  "#founding-partners": "/contact#pilot",
};

function useLegacyHashRedirect() {
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    const target = LEGACY_HASH_REDIRECTS[location.hash];
    if (target) navigate(target, { replace: true });
  }, [location.hash, navigate]);
}

export default function HomePage() {
  const { isAuthenticated, loading } = useAuth();
  useLegacyHashRedirect();
  const assistantConfig = useSiteAssistantConfig({ enabled: !loading && !isAuthenticated });

  const hero = getSection("home.hero");
  const browseInstead = getSection("home.browse-instead");
  const whatYouGetBack = getSection("home.what-you-get-back");
  const valuesSummary = getSection("home.values-summary");
  const pilotTeaser = getSection("home.pilot-teaser");

  if (loading) return <div>Loading...</div>;
  if (isAuthenticated) return <Navigate to="/dashboard" replace />;

  return (
    <>
      <title>Open Grant Flow</title>
      <div className="bg-brand-off-white">
        <SectionVisibility section={hero}>
          {(hero) => <ClassicHero section={hero} />}
        </SectionVisibility>

        {assistantConfig.data?.enabled && (
          <SiteAssistantBox maxQuestionChars={assistantConfig.data.max_question_chars} />
        )}

        <SectionVisibility section={browseInstead}>
          {(browseInstead) => (
            <SiteSection id={browseInstead.anchor} alt className="text-center">
              <h2 className="text-site-h2 mb-12 text-brand-slate">{browseInstead.title}</h2>
              <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
                {browseInstead.items?.map((item) => (
                  <Link
                    key={item.title}
                    to={item.href ?? "/"}
                    className="rounded-2xl bg-white p-6 text-left card-shadow-lg hover:opacity-90"
                  >
                    <h3 className="mb-2 font-semibold text-brand-slate">{item.title}</h3>
                    <p className="text-sm text-slate-500">{item.body}</p>
                  </Link>
                ))}
              </div>
            </SiteSection>
          )}
        </SectionVisibility>

        <SectionVisibility section={whatYouGetBack}>
          {(whatYouGetBack) => (
            <SiteSection id={whatYouGetBack.anchor} alt>
              <SectionHead eyebrow={whatYouGetBack.eyebrow} title={whatYouGetBack.title} />
              <ul className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
                {whatYouGetBack.items?.map((item) => (
                  <li key={item.title} className="grid content-start gap-2.5 rounded-2xl bg-white p-6 card-shadow-lg">
                    <h3 className="text-lg font-semibold leading-snug text-brand-slate">{item.title}</h3>
                    <p className="text-slate-500">{item.body}</p>
                  </li>
                ))}
              </ul>
            </SiteSection>
          )}
        </SectionVisibility>

        <SectionVisibility section={valuesSummary}>
          {(valuesSummary) => (
            <SiteSection id={valuesSummary.anchor}>
              <SectionHead eyebrow={valuesSummary.eyebrow} title={valuesSummary.title} />
              <ul className="grid gap-6 md:grid-cols-2">
                {valuesSummary.items?.map((item) => (
                  <li key={item.title} className="grid content-start gap-2 rounded-2xl bg-white p-6 card-shadow-lg">
                    <h3 className="text-lg font-semibold leading-snug text-brand-slate">{item.title}</h3>
                    <p className="text-slate-500">{item.body}</p>
                  </li>
                ))}
              </ul>
              <div className="mt-8 font-semibold text-brand-navy [&_a]:underline">
                <SiteMarkdown>{valuesSummary.body}</SiteMarkdown>
              </div>
            </SiteSection>
          )}
        </SectionVisibility>

        <SectionVisibility section={pilotTeaser}>
          {(pilotTeaser) => (
            <CtaBand
              id={pilotTeaser.anchor}
              title={pilotTeaser.title}
              body={<SiteMarkdown>{pilotTeaser.body}</SiteMarkdown>}
              cta={{
                label: pilotTeaser.items?.[0]?.title ?? "Request a demo",
                to: pilotTeaser.items?.[0]?.href ?? "/contact",
              }}
            />
          )}
        </SectionVisibility>
      </div>
    </>
  );
}
