import { brand } from "@/lib/brand";

const LAST_UPDATED = "August 2026";

export default function LegalPage() {
  return (
    <main
      className="max-w-3xl mx-auto px-6 py-16 space-y-20"
      style={{ color: brand.slate }}
    >
      <section id="privacy">
        <h1 className="text-3xl font-bold mb-2">Privacy Policy</h1>
        <p className="text-sm text-slate-500 mb-8">
          Last updated: {LAST_UPDATED}
        </p>

        <div className="space-y-6">
          <p>
            Open Grant Flow ("we", "us") is an open-source grant financial
            management platform, currently in active development. This
            policy explains what information we collect and how we use it.
          </p>

          <div>
            <h2 className="font-semibold mb-2">Legal status</h2>
            <p>
              Open Grant Flow is operated by its maintainer as an
              open-source project and is not yet a registered legal entity
              (company or nonprofit). This may change as the project
              develops.
            </p>
          </div>

          <div>
            <h2 className="font-semibold mb-2">Information we collect</h2>
            <p>
              When you submit our contact form, we collect your name,
              organisation, email address, role and message. If you use our
              hosted platform, we collect the account and budget information
              needed to provide the service.
            </p>
          </div>

          <div>
            <h2 className="font-semibold mb-2">How we use it</h2>
            <p>
              We use this information solely to respond to your enquiry, to
              operate the hosted platform, and to improve Open Grant Flow.
              We do not sell your information to third parties.
            </p>
          </div>

          <div>
            <h2 className="font-semibold mb-2">Self-hosting</h2>
            <p>
              Open Grant Flow is open source. If you self-host the
              platform, your data stays on your own infrastructure and this
              policy does not apply to it.
            </p>
          </div>

          <div>
            <h2 className="font-semibold mb-2">How long we keep it</h2>
            <p>
              We retain your information only for as long as needed to
              provide the service, respond to your enquiry, or meet legal
              and institutional record-keeping obligations. We don't yet
              publish a fixed retention schedule; this is being finalized
              as the platform matures.
            </p>
          </div>

          <div>
            <h2 className="font-semibold mb-2">Third-party processors</h2>
            <p>
              We use a small number of third-party services to operate the
              hosted platform: Hetzner (infrastructure, EU), Mailjet and
              MailerSend (transactional email, EU), Anthropic (AI-assisted
              features, when you supply your own API key — this involves a
              transfer of data outside the EU/EEA to the US), and Grafana
              Cloud (operational monitoring). Each only receives the data
              needed to provide its service.
            </p>
          </div>

          <div>
            <h2 className="font-semibold mb-2">Contact</h2>
            <p>
              Questions about this policy can be sent to{" "}
              <a
                href="mailto:privacy@opengrantflow.com"
                className="underline hover:opacity-70"
              >
                privacy@opengrantflow.com
              </a>{" "}
              or through our{" "}
              <a href="/#contact" className="underline hover:opacity-70">
                contact form
              </a>
              .
            </p>
          </div>
        </div>
      </section>

      <section id="terms">
        <h1 className="text-3xl font-bold mb-2">Terms of Service</h1>
        <p className="text-sm text-slate-500 mb-8">
          Last updated: {LAST_UPDATED}
        </p>

        <div className="space-y-6">
          <p>
            By using Open Grant Flow, you agree to these terms. If you do
            not agree, please do not use the platform.
          </p>

          <div>
            <h2 className="font-semibold mb-2">The service</h2>
            <p>
              Open Grant Flow is open-source software, currently in active
              development. Features, availability and functionality may
              change as the platform evolves.
            </p>
          </div>

          <div>
            <h2 className="font-semibold mb-2">No warranty</h2>
            <p>
              The platform is provided "as is", without warranty of any
              kind, express or implied, including during this active
              development phase.
            </p>
          </div>

          <div>
            <h2 className="font-semibold mb-2">Acceptable use</h2>
            <p>
              You agree to use Open Grant Flow only for lawful purposes and
              not to misuse the platform or attempt to disrupt its
              operation.
            </p>
          </div>

          <div>
            <h2 className="font-semibold mb-2">Changes to these terms</h2>
            <p>
              We may update these terms as the platform develops. Continued
              use of Open Grant Flow after changes means you accept the
              updated terms.
            </p>
          </div>

          <div>
            <h2 className="font-semibold mb-2">Contact</h2>
            <p>
              Questions about these terms can be sent through our{" "}
              <a href="/#contact" className="underline hover:opacity-70">
                contact form
              </a>
              .
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}
