import { useEffect } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { getSection } from "@/lib/siteContent";
import { SiteMarkdown } from "@/components/site/SiteMarkdown";
import { SectionVisibility } from "@/components/site/SectionVisibility";
import { ClassicHero } from "@/components/site/ClassicHero";
import { SiteSection } from "@/components/site/SiteSection";
import { SectionHead } from "@/components/site/SectionHead";
import { SectionCtaBand } from "@/components/site/CtaBand";
import { AssistantHero, HeroPlaceholder } from "@/components/site/AssistantHero";
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
  const askHero = getSection("home.ask-hero");
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
        {assistantConfig.isPending ? (
          <HeroPlaceholder />
        ) : assistantConfig.data?.enabled && askHero ? (
          <SectionVisibility section={askHero}>
            {(askHero) => (
              <AssistantHero
                section={askHero}
                browseInstead={browseInstead}
                maxQuestionChars={assistantConfig.data.max_question_chars}
              />
            )}
          </SectionVisibility>
        ) : (
          <SectionVisibility section={hero}>
            {(hero) => <ClassicHero section={hero} />}
          </SectionVisibility>
        )}

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

        <SectionCtaBand section={pilotTeaser} />
      </div>
    </>
  );
}
