import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import {
  Wallet,
  Activity,
  Receipt,
  FileText,
  ShieldCheck,
  ArrowRight,
  User,
} from "lucide-react";
import productMockup from "@/assets/logos/opengrantflow-mockup.png";
import { brand } from "@/lib/brand";

const TONE_COLORS = {
  grey: { border: "#94A3B8", text: "#64748B" },
  orange: { border: brand.gold, text: "#92702B" },
  red: { border: "#DC2626", text: "#DC2626" },
} as const;

const WORKFLOW_STEPS: { label: string; tone: keyof typeof TONE_COLORS }[] = [
  { label: "Grant", tone: "grey" },
  { label: "Spreadsheet", tone: "grey" },
  { label: "Email", tone: "grey" },
  { label: "Updated Spreadsheet", tone: "grey" },
  { label: "Receipt Folder", tone: "grey" },
  { label: "Word Report", tone: "grey" },
  { label: "Questions", tone: "orange" },
  { label: "Corrections", tone: "orange" },
  { label: "Audit", tone: "red" },
];

const SECTOR_QUOTES = [
  {
    quote:
      "Even sophisticated internal systems can still require exporting files to grantees and bringing them back.",
    role: "Former UK fund CEO",
  },
  {
    quote:
      "Multiple platforms solve different pieces, but not the basic cross-organisation workflow.",
    role: "International nonprofit leader",
  },
  {
    quote:
      "A donor portal can digitise the funder side while the grantee still keeps separate local records.",
    role: "Nonprofit / fund adviser",
  },
];

const AUDIENCES = [
  {
    emoji: "🏛",
    title: "Institutional Donors",
    description: "Manage grant portfolios more efficiently.",
  },
  {
    emoji: "🤝",
    title: "Foundations",
    description: "Reduce reporting burden for grantees.",
  },
  {
    emoji: "🌍",
    title: "International NGOs",
    description: "Standardise financial reporting.",
  },
  {
    emoji: "🏢",
    title: "Nonprofits",
    description: "Spend less time on administration.",
  },
];

const FEATURES = [
  {
    icon: Wallet,
    title: "Budget",
    description:
      "Create structured project budgets with optional AI assistance.",
  },
  {
    icon: Activity,
    title: "Track",
    description: "Record spending against approved budget lines.",
  },
  {
    icon: Receipt,
    title: "Receipts",
    description:
      "Keep receipts and supporting documents connected to every transaction.",
  },
  {
    icon: FileText,
    title: "Report",
    description:
      "Generate donor-ready financial reports without rebuilding spreadsheets.",
  },
  {
    icon: ShieldCheck,
    title: "Audit Ready",
    description:
      "Maintain a transparent financial history that simplifies audits and reviews.",
  },
];

const OPEN_SOURCE_ITEMS = [
  "use our hosted platform",
  "self-host",
  "contribute",
  "inspect the source code",
];

const IDEAL_PARTNERS = [
  "institutional donors",
  "grant-making foundations",
  "international NGOs",
  "nonprofit organisations",
];

const PARTNER_BENEFITS = [
  "direct collaboration with the founder",
  "early access",
  "influence over product direction",
  "pilot opportunities",
  "discounted hosted services when available",
];

const ROLE_OPTIONS = [
  "Institutional Donor",
  "Foundation",
  "Nonprofit",
  "NGO",
  "Technology Partner",
  "Volunteer",
  "Other",
];

function Kicker({ children }: { children: React.ReactNode }) {
  return (
    <p
      className="text-xs font-semibold tracking-widest uppercase mb-3"
      style={{ color: brand.gold }}
    >
      {children}
    </p>
  );
}

function Hero() {
  return (
    <section className="max-w-6xl mx-auto px-6 py-20 text-center">
      <div className="max-w-3xl mx-auto">
        <h1
          className="text-4xl md:text-5xl font-bold mb-6 leading-tight"
          style={{ color: brand.slate }}
        >
          Grant management without spreadsheets.
        </h1>

        <p
          className="text-lg mb-2 max-w-2xl mx-auto"
          style={{ color: brand.slate }}
        >
          Open Grant Flow helps nonprofits and institutional donors manage the
          complete financial lifecycle of a grant—from budgeting and spending to
          reporting and audit readiness.
        </p>
        <p className="text-lg mb-10" style={{ color: brand.slate }}>
          Built from 17 years of nonprofit leadership and grant management
          experience.
        </p>

        <div className="flex flex-wrap justify-center gap-4">
          <a
            href="#founding-partners"
            className="rounded-lg px-6 py-3 font-medium text-white transition-opacity hover:opacity-90"
            style={{ backgroundColor: brand.navy }}
          >
            Become a Founding Design Partner
          </a>
          <a
            href="#problem"
            className="rounded-lg px-6 py-3 font-medium border transition-colors hover:bg-slate-50"
            style={{ borderColor: brand.navy, color: brand.navy }}
          >
            Learn More
          </a>
        </div>
      </div>

      <img
        src={productMockup}
        alt="Open Grant Flow budgets dashboard with the AI budget assistant panel"
        // className="w-full rounded-xl shadow-2xl border border-slate-200 mt-16"
      />
      <p className="text-sm text-slate-500 mt-4">
        Budgets, tracking and reporting in one place — with optional AI
        assistance for faster setup.
      </p>
    </section>
  );
}

function DemoSection() {
  return (
    <section id="demo" className="max-w-4xl mx-auto px-6 py-16">
      <div className="text-center mb-10">
        <Kicker>See It In Action</Kicker>
        <h2 className="text-3xl font-bold" style={{ color: brand.slate }}>
          Watch a 30 seconds product tour
        </h2>
      </div>
      <div className="relative w-full aspect-video rounded-xl shadow-2xl border border-slate-200 overflow-hidden">
        <iframe
          src="https://demo.arcade.software/video/bJX6Bh5bfgTZU5E2pUSK?embed&embed_mobile=inline&embed_desktop=inline&show_copy_link=true"
          title="OpenGrantFlow - Grant Management Without Spreadsheets"
          loading="lazy"
          allow="clipboard-write; autoplay"
          allowFullScreen
          className="absolute inset-0 h-full w-full"
        />
      </div>
    </section>
  );
}

function AudienceSection() {
  return (
    <section className="px-6 py-16" style={{ backgroundColor: "#EEF2F6" }}>
      <div className="max-w-5xl mx-auto text-center">
        <Kicker>Who Is This For</Kicker>
        <h2 className="text-3xl font-bold mb-12" style={{ color: brand.slate }}>
          Who is this for?
        </h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {AUDIENCES.map(({ emoji, title, description }) => (
            <div
              key={title}
              className="bg-white p-6 rounded-2xl card-shadow-lg text-left"
            >
              <div className="text-3xl mb-4">{emoji}</div>
              <h3 className="font-semibold mb-2" style={{ color: brand.slate }}>
                {title}
              </h3>
              <p className="text-sm text-slate-500">{description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function ProblemSection() {
  return (
    <section id="problem" className="max-w-4xl mx-auto px-6 py-16">
      <Kicker>The Problem</Kicker>
      <p className="text-xl font-medium mb-3" style={{ color: brand.slate }}>
        Every grant creates another spreadsheet.
      </p>
      <h2 className="text-3xl font-bold mb-6" style={{ color: brand.slate }}>
        Grant reporting is still too complicated
      </h2>
      <div className="space-y-4 mb-12 max-w-2xl" style={{ color: brand.slate }}>
        <p>
          Many grant-funded organisations still rely on spreadsheets, donor
          templates, email threads and manual reconciliation.
        </p>
        <p>
          This creates unnecessary administrative work for both nonprofits and
          donors.
        </p>
        <p>
          Instead of focusing on delivering impact, organisations spend valuable
          time preparing financial reports.
        </p>
      </div>

      <div className="bg-white rounded-2xl card-shadow-lg p-8">
        <p
          className="text-xs font-semibold tracking-widest uppercase mb-4 text-center"
          style={{ color: brand.slate }}
        >
          Current workflow
        </p>
        <ol className="flex flex-wrap items-center justify-center gap-y-3">
          {WORKFLOW_STEPS.map(({ label, tone }, i) => {
            const next = WORKFLOW_STEPS[i + 1];
            return (
              <li key={label} className="flex items-center">
                <span
                  className="rounded-full border px-4 py-1.5 text-sm whitespace-nowrap font-medium"
                  style={{
                    borderColor: TONE_COLORS[tone].border,
                    color: TONE_COLORS[tone].text,
                  }}
                >
                  {label}
                </span>
                {next && (
                  <ArrowRight
                    size={16}
                    className="mx-3 flex-shrink-0"
                    style={{ color: TONE_COLORS[next.tone].border }}
                  />
                )}
              </li>
            );
          })}
        </ol>
      </div>

      <div className="mt-16">
        <p
          className="text-xs font-semibold tracking-widest uppercase mb-6"
          style={{ color: brand.teal }}
        >
          From conversations across the sector
        </p>

        <div className="grid sm:grid-cols-3 gap-5">
          {SECTOR_QUOTES.map(({ quote, role }) => (
            <div
              key={role}
              className="bg-white rounded-2xl card-shadow-lg p-6 flex flex-col gap-4"
            >
              <p className="italic flex-grow" style={{ color: brand.slate }}>
                &ldquo;{quote}&rdquo;
              </p>
              <p className="text-sm font-semibold" style={{ color: brand.teal }}>
                {role}
              </p>
            </div>
          ))}
        </div>

        <div
          className="mt-5 rounded-2xl p-6"
          style={{ backgroundColor: "#EDF6F3", border: "1px solid #CDE7DE" }}
        >
          <p className="mb-3" style={{ color: brand.slate }}>
            One leader of a small local nonprofit told us they went looking for
            an alternative and couldn&apos;t find one that fit — a sign the
            willingness is already there, once the right tool exists.
          </p>
          <p className="text-sm font-semibold" style={{ color: brand.teal }}>
            From a conversation with a local nonprofit leader
          </p>
        </div>

        <p
          className="mt-10 text-center text-xl font-bold"
          style={{ color: brand.teal }}
        >
          The emerging opportunity: interoperability, not another closed
          portal.
        </p>
      </div>
    </section>
  );
}

function SolutionSection() {
  return (
    <section
      id="platform"
      className="px-6 py-16"
      style={{ backgroundColor: "#EEF2F6" }}
    >
      <div className="max-w-5xl mx-auto">
        <Kicker>The Platform</Kicker>
        <h2 className="text-3xl font-bold mb-4" style={{ color: brand.slate }}>
          One platform for the entire grant lifecycle
        </h2>
        <p className="mb-12 max-w-2xl" style={{ color: brand.slate }}>
          Open Grant Flow provides one structured financial record from approved
          budget through donor reporting.
        </p>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {FEATURES.map(({ icon: Icon, title, description }) => (
            <div
              key={title}
              className="bg-white p-6 rounded-2xl card-shadow-lg text-left"
            >
              <div
                className="p-3 rounded-lg inline-block mb-4 bg-brand-navy/8"
              >
                <Icon size={22} style={{ color: brand.navy }} />
              </div>
              <h3 className="font-semibold mb-2" style={{ color: brand.slate }}>
                {title}
              </h3>
              <p className="text-sm text-slate-500">{description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function VisionSection() {
  return (
    <section id="vision" className="max-w-3xl mx-auto px-6 py-16">
      <Kicker>Our Vision</Kicker>
      <h2 className="text-3xl font-bold mb-6" style={{ color: brand.slate }}>
        Our Vision
      </h2>
      <div className="space-y-4" style={{ color: brand.slate }}>
        <p>
          We believe grant management should be collaborative rather than
          administrative.
        </p>
        <p>
          Instead of exchanging spreadsheets and emails, donors and nonprofits
          should share one transparent financial record.
        </p>
        <p>
          Open Grant Flow is building open financial infrastructure for
          grant-funded organisations.
        </p>
      </div>
    </section>
  );
}

function OpenSourceSection() {
  return (
    <section className="px-6 py-16" style={{ backgroundColor: "#EEF2F6" }}>
      <div className="max-w-3xl mx-auto">
        <Kicker>Transparency</Kicker>
        <h2 className="text-3xl font-bold mb-6" style={{ color: brand.slate }}>
          Open by Design
        </h2>
        <div className="space-y-4 mb-6" style={{ color: brand.slate }}>
          <p>
            Financial infrastructure for the nonprofit sector should be
            transparent and accessible.
          </p>
          <p>Open Grant Flow is open source. Organisations can:</p>
        </div>
        <ul
          className="list-disc list-inside space-y-2 mb-6"
          style={{ color: brand.slate }}
        >
          {OPEN_SOURCE_ITEMS.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        <p className="font-semibold" style={{ color: brand.teal }}>
          Transparency builds trust.
        </p>
      </div>
    </section>
  );
}

function FounderSection() {
  return (
    <section id="about" className="max-w-3xl mx-auto px-6 py-16">
      <Kicker>About</Kicker>
      <h2 className="text-3xl font-bold mb-8" style={{ color: brand.slate }}>
        Built from lived experience
      </h2>
      <div className="flex flex-col sm:flex-row gap-8 items-start">
        <div
          className="shrink-0 h-24 w-24 rounded-full flex items-center justify-center"
          style={{ backgroundColor: "#EEF2F6" }}
        >
          <User size={36} style={{ color: brand.slate }} />
        </div>
        <div className="space-y-4" style={{ color: brand.slate }}>
          <p>
            Open Grant Flow is founded by a software engineer who previously
            spent 17 years co-founding and leading nonprofit organisations in
            Armenia.
          </p>
          <p>
            During that time, hundreds of grant budgets, donor reports and
            financial reconciliations revealed the same recurring problem:
          </p>
          <p className="font-semibold">
            Too much time is spent managing administration instead of delivering
            impact.
          </p>
          <p className="italic">
            Open Grant Flow is the platform I wish had existed.
          </p>
        </div>
      </div>
    </section>
  );
}

function PartnerSection() {
  return (
    <section
      id="founding-partners"
      className="px-6 py-16"
      style={{ backgroundColor: "#EEF2F6" }}
    >
      <div className="max-w-3xl mx-auto">
        <Kicker>Founding Partners</Kicker>
        <h2 className="text-3xl font-bold mb-6" style={{ color: brand.slate }}>
          Become a Founding Design Partner
        </h2>
        <p className="mb-8" style={{ color: brand.slate }}>
          We&apos;re looking for a small number of organisations to help shape
          Open Grant Flow.
        </p>

        <div className="grid sm:grid-cols-2 gap-8 mb-8">
          <div>
            <h3 className="font-semibold mb-3" style={{ color: brand.slate }}>
              Ideal partners include
            </h3>
            <ul
              className="list-disc list-inside space-y-2"
              style={{ color: brand.slate }}
            >
              {IDEAL_PARTNERS.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
          <div>
            <h3 className="font-semibold mb-3" style={{ color: brand.slate }}>
              Partners will receive
            </h3>
            <ul
              className="list-disc list-inside space-y-2"
              style={{ color: brand.slate }}
            >
              {PARTNER_BENEFITS.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        </div>

        <div
          className="bg-white rounded-xl p-5 border-l-4"
          style={{ borderColor: brand.gold }}
        >
          <p className="italic" style={{ color: brand.slate }}>
            This is not a sales programme. It is a collaborative product
            development initiative.
          </p>
        </div>
      </div>
    </section>
  );
}

function ContactSection() {
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(false);

  const inputClass =
    "w-full px-4 py-2 border border-slate-300 rounded-lg bg-white input-focus";

  const accessKey = import.meta.env.VITE_WEB3FORMS_ACCESS_KEY;

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(false);

    const formData = new FormData(e.currentTarget);

    try {
      const res = await fetch("https://api.web3forms.com/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          access_key: accessKey,
          subject: "New Open Grant Flow enquiry",
          name: formData.get("name"),
          organisation: formData.get("organisation"),
          email: formData.get("email"),
          role: formData.get("role"),
          message: formData.get("message"),
          request_demo: formData.get("request_demo") === "on",
        }),
      });
      if (!res.ok) throw new Error("submission failed");
      setSubmitted(true);
    } catch {
      setError(true);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section id="contact" className="max-w-2xl mx-auto px-6 py-16">
      <Kicker>Contact</Kicker>
      <h2 className="text-3xl font-bold mb-8" style={{ color: brand.slate }}>
        Start a conversation
      </h2>

      {submitted ? (
        <div className="bg-white rounded-2xl card-shadow-lg p-8 text-center">
          <p style={{ color: brand.slate }}>
            Thank you — we&apos;ve received your message and will be in touch.
          </p>
        </div>
      ) : (
        <form
          onSubmit={handleSubmit}
          className="bg-white rounded-2xl card-shadow-lg p-8 space-y-5"
        >
          <div>
            <label
              htmlFor="name"
              className="block text-sm font-medium mb-2"
              style={{ color: brand.slate }}
            >
              Name
            </label>
            <input
              id="name"
              name="name"
              type="text"
              required
              className={inputClass}
            />
          </div>
          <div>
            <label
              htmlFor="organisation"
              className="block text-sm font-medium mb-2"
              style={{ color: brand.slate }}
            >
              Organisation
            </label>
            <input
              id="organisation"
              name="organisation"
              type="text"
              required
              className={inputClass}
            />
          </div>
          <div>
            <label
              htmlFor="email"
              className="block text-sm font-medium mb-2"
              style={{ color: brand.slate }}
            >
              Email
            </label>
            <input
              id="email"
              name="email"
              type="email"
              required
              className={inputClass}
            />
          </div>
          <div>
            <label
              htmlFor="role"
              className="block text-sm font-medium mb-2"
              style={{ color: brand.slate }}
            >
              Role
            </label>
            <select
              id="role"
              name="role"
              required
              defaultValue=""
              className={inputClass}
            >
              <option value="" disabled>
                Select a role
              </option>
              {ROLE_OPTIONS.map((role) => (
                <option key={role} value={role}>
                  {role}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label
              htmlFor="message"
              className="block text-sm font-medium mb-2"
              style={{ color: brand.slate }}
            >
              Message
            </label>
            <textarea
              id="message"
              name="message"
              required
              rows={4}
              className={inputClass}
            />
          </div>
          <div className="flex items-center gap-2">
            <input
              id="request-demo"
              name="request_demo"
              type="checkbox"
              className="h-4 w-4 rounded border-slate-300"
            />
            <label
              htmlFor="request-demo"
              className="text-sm"
              style={{ color: brand.slate }}
            >
              I&apos;d like to request a demo
            </label>
          </div>

          {error && (
            <p className="text-sm text-red-600">
              Something went wrong sending your message. Please try again, or
              email us directly.
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg px-6 py-3 font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
            style={{ backgroundColor: brand.navy }}
          >
            {submitting ? "Sending…" : "Let's Start a Conversation"}
          </button>
        </form>
      )}
    </section>
  );
}

export default function LandingPage() {
  const { isAuthenticated, loading } = useAuth();

  if (loading) return <div>Loading...</div>;
  if (isAuthenticated) return <Navigate to="/dashboard" replace />;

  return (
    <>
      <Hero />
      <DemoSection />
      <AudienceSection />
      <ProblemSection />
      <SolutionSection />
      <VisionSection />
      <OpenSourceSection />
      <FounderSection />
      <PartnerSection />
      <ContactSection />
    </>
  );
}
