import { useEffect } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { getSection } from "@/lib/siteContent";
import { SiteMarkdown } from "@/components/site/SiteMarkdown";
import { SectionVisibility } from "@/components/site/SectionVisibility";
import { ProductDemo } from "@/components/site/ProductDemo";
import productMockup from "@/assets/logos/opengrantflow-mockup.png";

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
          {(hero) => (
            <section
              id={hero.anchor}
              className="max-w-6xl mx-auto px-6 py-20 text-center"
            >
              <div className="max-w-3xl mx-auto">
                <h1 className="text-4xl md:text-5xl font-bold mb-6 leading-tight text-brand-slate">
                  {hero.title}
                </h1>
                <div className="text-lg mb-10 max-w-2xl mx-auto text-brand-slate">
                  <SiteMarkdown>{hero.body}</SiteMarkdown>
                </div>
                <div className="flex flex-wrap justify-center gap-4">
                  {hero.items?.map((item) => (
                    <Link
                      key={item.title}
                      to={item.href ?? "/"}
                      className="rounded-lg px-6 py-3 font-medium text-white transition-opacity hover:opacity-90 bg-brand-navy"
                    >
                      {item.title}
                    </Link>
                  ))}
                </div>
              </div>
              <img
                src={productMockup}
                alt="Open Grant Flow budgets dashboard with the AI budget assistant panel"
                className="mt-16"
              />
            </section>
          )}
        </SectionVisibility>

        <ProductDemo />

        <SectionVisibility section={browseInstead}>
          {(browseInstead) => (
            <section id={browseInstead.anchor} className="px-6 py-16 bg-brand-mist">
              <div className="max-w-5xl mx-auto text-center">
                <h2 className="text-3xl font-bold mb-12 text-brand-slate">
                  {browseInstead.title}
                </h2>
                <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
                  {browseInstead.items?.map((item) => (
                    <Link
                      key={item.title}
                      to={item.href ?? "/"}
                      className="bg-white p-6 rounded-2xl card-shadow-lg text-left hover:opacity-90"
                    >
                      <h3 className="font-semibold mb-2 text-brand-slate">
                        {item.title}
                      </h3>
                      <p className="text-sm text-slate-500">{item.body}</p>
                    </Link>
                  ))}
                </div>
              </div>
            </section>
          )}
        </SectionVisibility>

        <SectionVisibility section={whatYouGetBack}>
          {(whatYouGetBack) => (
            <section id={whatYouGetBack.anchor} className="max-w-5xl mx-auto px-6 py-16">
              <h2 className="text-3xl font-bold mb-12 text-center text-brand-slate">
                {whatYouGetBack.title}
              </h2>
              <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
                {whatYouGetBack.items?.map((item, index) => (
                  <div
                    key={index}
                    className="bg-white p-6 rounded-2xl card-shadow-lg text-left"
                  >
                    <h3 className="font-semibold mb-2 text-brand-slate">
                      {item.title}
                    </h3>
                    <p className="text-sm text-slate-500">{item.body}</p>
                  </div>
                ))}
              </div>
            </section>
          )}
        </SectionVisibility>

        <SectionVisibility section={valuesSummary}>
          {(valuesSummary) => (
            <section
              id={valuesSummary.anchor}
              className="px-6 py-16 bg-brand-mist"
            >
              <div className="max-w-5xl mx-auto">
                <h2 className="text-3xl font-bold mb-8 text-brand-slate">
                  {valuesSummary.title}
                </h2>
                <div className="grid sm:grid-cols-3 gap-6 mb-8">
                  {valuesSummary.items?.map((item, index) => (
                    <div
                      key={index}
                      className="bg-white p-6 rounded-2xl card-shadow-lg"
                    >
                      <h3 className="font-semibold mb-2 text-brand-slate">
                        {item.title}
                      </h3>
                      <p className="text-sm text-slate-500">{item.body}</p>
                    </div>
                  ))}
                </div>
                <div className="[&_a]:underline text-brand-slate">
                  <SiteMarkdown>{valuesSummary.body}</SiteMarkdown>
                </div>
              </div>
            </section>
          )}
        </SectionVisibility>

        <SectionVisibility section={pilotTeaser}>
          {(pilotTeaser) => (
            <section
              id={pilotTeaser.anchor}
              className="max-w-3xl mx-auto px-6 py-16 text-center"
            >
              <h2 className="text-3xl font-bold mb-6 text-brand-slate">
                {pilotTeaser.title}
              </h2>
              <div className="mb-8 text-brand-slate">
                <SiteMarkdown>{pilotTeaser.body}</SiteMarkdown>
              </div>
              {pilotTeaser.items?.map((item) => (
                <Link
                  key={item.title}
                  to={item.href ?? "/contact"}
                  className="inline-block rounded-lg px-6 py-3 font-medium text-white transition-opacity hover:opacity-90 bg-brand-navy"
                >
                  {item.title}
                </Link>
              ))}
            </section>
          )}
        </SectionVisibility>
      </div>
    </>
  );
}
