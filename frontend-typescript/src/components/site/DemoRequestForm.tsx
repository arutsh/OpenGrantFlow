import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

const ORGANISATION_TYPES = [
  "Nonprofit or NGO",
  "Foundation",
  "Institutional donor",
  "Other",
];

const inputClass =
  "w-full px-4 py-2 border border-slate-300 rounded-lg bg-white input-focus aria-[invalid=true]:border-red-500";

function FieldLabel({ htmlFor, children }: { htmlFor: string; children: string }) {
  return (
    <label
      htmlFor={htmlFor}
      className="block text-sm font-medium mb-2 text-brand-slate"
    >
      {children}
    </label>
  );
}

export function DemoRequestForm() {
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(false);
  const [invalidFields, setInvalidFields] = useState<Set<string>>(new Set());

  const accessKey = import.meta.env.VITE_WEB3FORMS_ACCESS_KEY;

  function flagInvalid(name: string) {
    setInvalidFields((fields) => new Set(fields).add(name));
  }

  function clearInvalid(name: string) {
    setInvalidFields((fields) => {
      if (!fields.has(name)) return fields;
      const next = new Set(fields);
      next.delete(name);
      return next;
    });
  }

  const fieldProps = (name: string) => ({
    name,
    "aria-invalid": invalidFields.has(name),
    onInvalid: () => flagInvalid(name),
    onChange: () => clearInvalid(name),
    className: inputClass,
  });

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
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
          subject: "New Open Grant Flow demo request",
          name: formData.get("name"),
          email: formData.get("email"),
          organisation: formData.get("organisation"),
          organisation_type: formData.get("organisation_type"),
          reporting_time: formData.get("reporting_time"),
          pilot_interest: formData.get("pilot_interest") === "on",
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

  if (submitted) {
    return (
      <div className="bg-white rounded-2xl card-shadow-lg p-8 text-center">
        <p className="text-brand-slate">
          Thank you — we&apos;ve received your request and will be in touch.
        </p>
      </div>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-white rounded-2xl card-shadow-lg p-8 space-y-5"
    >
      <div>
        <FieldLabel htmlFor="demo-name">Name</FieldLabel>
        <input id="demo-name" type="text" required {...fieldProps("name")} />
      </div>
      <div>
        <FieldLabel htmlFor="demo-email">Work email</FieldLabel>
        <input id="demo-email" type="email" required {...fieldProps("email")} />
      </div>
      <div>
        <FieldLabel htmlFor="demo-organisation">Organisation</FieldLabel>
        <input
          id="demo-organisation"
          type="text"
          required
          {...fieldProps("organisation")}
        />
      </div>
      <div>
        <FieldLabel htmlFor="demo-organisation-type">Organisation type</FieldLabel>
        <select
          id="demo-organisation-type"
          required
          defaultValue=""
          {...fieldProps("organisation_type")}
        >
          <option value="" disabled>
            Select an organisation type
          </option>
          {ORGANISATION_TYPES.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
      </div>
      <div>
        <FieldLabel htmlFor="demo-reporting-time">
          How long does a donor report take your team today? (optional)
        </FieldLabel>
        <textarea
          id="demo-reporting-time"
          name="reporting_time"
          rows={3}
          className={inputClass}
        />
      </div>
      <div className="flex items-center gap-2">
        <input
          id="demo-pilot-interest"
          name="pilot_interest"
          type="checkbox"
          className="h-4 w-4 rounded border-slate-300"
        />
        <label
          htmlFor="demo-pilot-interest"
          className="text-sm text-brand-slate"
        >
          I&apos;m interested in becoming a Pilot Partner
        </label>
      </div>

      <p className="text-xs text-slate-500">
        We use these details only to reply to your request. See our{" "}
        <Link to="/legal#privacy" className="underline hover:opacity-70">
          privacy policy
        </Link>
        .
      </p>

      {error && (
        <p className="text-sm text-red-600">
          Something went wrong sending your request. Please try again, or email
          us directly.
        </p>
      )}

      <button
        type="submit"
        disabled={submitting}
        className="w-full rounded-lg px-6 py-3 font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50 bg-brand-navy"
      >
        {submitting ? "Sending…" : "Request a demo"}
      </button>
    </form>
  );
}
