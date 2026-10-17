import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { getSection } from "@/lib/siteContent";
import {
  classifySiteAssistantError,
  useAskSiteAssistant,
  type SiteAssistantFailure,
  type SiteAssistantPersona,
} from "@/api/siteAssistantApi";

const PERSONAS: { value: SiteAssistantPersona | null; label: string }[] = [
  { value: null, label: "Anyone" },
  { value: "grantee", label: "Grantee" },
  { value: "funder", label: "Funder" },
  { value: "technical", label: "Technical" },
];

// Same links as Home's own Browse-instead cards, so renames stay in one content file.
function browseLinks() {
  const items = getSection("home.browse-instead")?.items ?? [];
  return items.flatMap((item) =>
    item.title && item.href ? [{ to: item.href, label: item.title }] : [],
  );
}

// Resolving against the origin also catches "/\host" and other forms browsers treat as off-site.
function isSitePath(url: string): boolean {
  if (!url.startsWith("/")) return false;
  try {
    return new URL(url, window.location.origin).origin === window.location.origin;
  } catch {
    return false;
  }
}

const FALLBACK_MESSAGES: Record<SiteAssistantFailure | "unanswerable", string> = {
  unanswerable: "Sorry, I couldn't find that on this site. Try browsing instead:",
  daily_cap: "The assistant has answered all it can for today. Try again tomorrow, or browse:",
  unavailable: "The assistant isn't available right now. You can browse instead:",
  error: "Something went wrong asking the assistant. You can browse instead:",
};

function BrowseInstead({ message }: { message: string }) {
  return (
    <div>
      <p className="mb-3 text-brand-slate">{message}</p>
      <ul className="flex flex-wrap gap-2">
        {browseLinks().map((link) => (
          <li key={link.to}>
            <Link
              to={link.to}
              className="inline-block rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-brand-slate hover:bg-brand-mist"
            >
              {link.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function SiteAssistantBox({ maxQuestionChars }: { maxQuestionChars: number }) {
  const [question, setQuestion] = useState("");
  const [persona, setPersona] = useState<SiteAssistantPersona | null>(null);
  const ask = useAskSiteAssistant();

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || ask.isPending) return;
    ask.mutate({ question: trimmed, persona });
  }

  const answer = ask.data;
  // Server citation URLs are site paths; anything else is dropped rather than linked.
  const citations = answer?.citations.filter((c) => isSitePath(c.url));

  return (
    <section id="ask" className="px-6 py-16">
      <div className="max-w-3xl mx-auto bg-white rounded-2xl card-shadow-lg p-6 sm:p-8">
        <h2 className="text-2xl font-bold mb-2 text-brand-slate">Ask about Open Grant Flow</h2>
        <p className="text-xs text-slate-500 mb-6">
          Questions are sent to an AI provider to generate an answer from this website&apos;s
          content, and are not stored by us. Please don&apos;t include personal details. See our{" "}
          <Link to="/legal#privacy-processors" className="underline hover:opacity-70">
            privacy policy
          </Link>
          .
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <fieldset>
            <legend className="text-sm font-medium mb-2 text-brand-slate">I am asking as</legend>
            <div className="flex flex-wrap gap-2">
              {PERSONAS.map((option) => (
                <button
                  key={option.label}
                  type="button"
                  aria-pressed={persona === option.value}
                  onClick={() => setPersona(option.value)}
                  className="rounded-full border px-4 py-1.5 text-sm transition-colors border-slate-300 text-brand-slate aria-pressed:bg-brand-navy aria-pressed:border-brand-navy aria-pressed:text-white"
                >
                  {option.label}
                </button>
              ))}
            </div>
          </fieldset>

          <div>
            <label
              htmlFor="site-assistant-question"
              className="block text-sm font-medium mb-2 text-brand-slate"
            >
              Your question
            </label>
            <textarea
              id="site-assistant-question"
              rows={3}
              maxLength={maxQuestionChars}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              className="w-full px-4 py-2 border border-slate-300 rounded-lg bg-white input-focus"
            />
            <p className="text-xs text-slate-500 text-right">
              {question.length}/{maxQuestionChars}
            </p>
          </div>

          <button
            type="submit"
            disabled={ask.isPending || !question.trim()}
            className="w-full sm:w-auto rounded-lg px-6 py-3 font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50 bg-brand-navy"
          >
            {ask.isPending ? "Asking…" : "Ask"}
          </button>
        </form>

        <div aria-live="polite" className="mt-6 empty:hidden">
          {ask.isError && (
            <BrowseInstead message={FALLBACK_MESSAGES[classifySiteAssistantError(ask.error)]} />
          )}
          {answer && !answer.answerable && (
            <BrowseInstead message={FALLBACK_MESSAGES.unanswerable} />
          )}
          {answer?.answerable && (
            <div className="rounded-xl bg-brand-mist p-4 sm:p-5">
              <p className="whitespace-pre-line text-brand-slate">{answer.answer}</p>
              {citations && citations.length > 0 && (
                <div className="mt-4">
                  <h3 className="text-sm font-semibold mb-2 text-brand-slate">Sources</h3>
                  <ul className="space-y-1">
                    {citations.map((citation) => (
                      <li key={citation.content_id}>
                        <Link
                          to={citation.url}
                          className="text-sm underline text-brand-navy hover:opacity-70"
                        >
                          {citation.title}
                        </Link>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
