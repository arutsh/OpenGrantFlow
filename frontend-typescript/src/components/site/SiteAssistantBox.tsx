import { useRef, useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { getSection } from "@/lib/siteContent";
import { assistantSuggestions } from "@/lib/assistantSuggestions";
import {
  classifySiteAssistantError,
  useAskSiteAssistant,
  type SiteAssistantCitation,
  type SiteAssistantFailure,
  type SiteAssistantPersona,
} from "@/api/siteAssistantApi";

const PERSONAS: { value: SiteAssistantPersona | null; label: string }[] = [
  { value: null, label: "Anyone" },
  { value: "grantee", label: "I receive grants" },
  { value: "funder", label: "I fund grants" },
  { value: "technical", label: "I'm technical" },
];

const ANSWER_LABELS: Record<SiteAssistantPersona | "none", string> = {
  none: "Answer",
  grantee: "Answer for grant recipients",
  funder: "Answer for funders",
  technical: "Answer for technical teams",
};

const FALLBACK_MESSAGES: Record<SiteAssistantFailure | "unanswerable", string> = {
  unanswerable: "Sorry, I couldn't find that on this site. Try browsing instead:",
  daily_cap: "The assistant has answered all it can for today. Try again tomorrow, or browse:",
  unavailable: "The assistant isn't available right now. You can browse instead:",
  error: "Something went wrong asking the assistant. You can browse instead:",
};

// Show the character counter once the question reaches this share of the limit.
const COUNTER_THRESHOLD = 0.8;

// Same links as Home's browse-instead line, so renames stay in one content file.
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

function PersonaToggle({ persona, onChange }: {
  persona: SiteAssistantPersona | null;
  onChange: (persona: SiteAssistantPersona | null) => void;
}) {
  return (
    <div role="group" aria-label="I am asking as" className="flex flex-wrap justify-center gap-2">
      {PERSONAS.map((option) => (
        <button
          key={option.label}
          type="button"
          aria-pressed={persona === option.value}
          onClick={() => onChange(persona === option.value ? null : option.value)}
          className="rounded-full border border-slate-300 bg-white px-4 py-1.5 text-sm font-medium text-brand-slate transition-colors hover:border-brand-navy aria-pressed:border-brand-navy aria-pressed:bg-brand-navy aria-pressed:text-white"
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

function SuggestedQuestions({ questions, onPick }: {
  questions: string[];
  onPick: (question: string) => void;
}) {
  return (
    <ul aria-label="Suggested questions" className="flex flex-wrap gap-2">
      {questions.map((question) => (
        <li key={question}>
          <button
            type="button"
            onClick={() => onPick(question)}
            className="rounded-2xl border border-slate-200 bg-brand-off-white px-3 py-1.5 text-left text-sm leading-snug text-brand-slate hover:border-brand-teal hover:bg-brand-teal-tint"
          >
            {question}
          </button>
        </li>
      ))}
    </ul>
  );
}

function ResultFooter({ onReset }: { onReset: () => void }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-5 gap-y-2.5">
      <Link
        to="/contact"
        className="inline-flex min-h-10 items-center rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-brand-navy hover:bg-brand-mist"
      >
        Request a demo
      </Link>
      <button
        type="button"
        onClick={onReset}
        className="text-sm text-brand-navy underline hover:opacity-70"
      >
        Ask something else
      </button>
    </div>
  );
}

function ResultContainer({ children }: { children: ReactNode }) {
  return <div className="grid min-w-0 gap-2.5 border-t border-slate-200 pt-4">{children}</div>;
}

function AnswerBlock({ question, persona, answer, citations, onReset }: {
  question: string;
  persona: SiteAssistantPersona | null;
  answer: string;
  citations: SiteAssistantCitation[];
  onReset: () => void;
}) {
  return (
    <ResultContainer>
      <p className="text-xs font-semibold uppercase tracking-widest text-brand-teal">
        {ANSWER_LABELS[persona ?? "none"]}
      </p>
      <h3 className="text-lg font-semibold leading-snug text-brand-slate">{question}</h3>
      <p className="whitespace-pre-line text-brand-slate">{answer}</p>
      {citations.length > 0 && (
        <p className="text-sm text-slate-500">
          Answered from:{" "}
          {citations.map((citation, index) => (
            <span key={citation.content_id}>
              {index > 0 && " · "}
              <Link to={citation.url} className="text-brand-navy underline hover:opacity-70">
                {citation.title}
              </Link>
            </span>
          ))}
        </p>
      )}
      <ResultFooter onReset={onReset} />
    </ResultContainer>
  );
}

function FallbackBlock({ message, onReset }: { message: string; onReset: () => void }) {
  return (
    <ResultContainer>
      <p className="text-brand-slate">{message}</p>
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
      <ResultFooter onReset={onReset} />
    </ResultContainer>
  );
}

export function SiteAssistantBox({ maxQuestionChars }: { maxQuestionChars: number }) {
  const [question, setQuestion] = useState("");
  const [persona, setPersona] = useState<SiteAssistantPersona | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const ask = useAskSiteAssistant();

  function submit(text: string) {
    const trimmed = text.trim();
    if (!trimmed || ask.isPending) return;
    ask.mutate({ question: trimmed, persona });
  }

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    submit(question);
  }

  function pickSuggestion(text: string) {
    setQuestion(text);
    submit(text);
    // The clicked chip unmounts once the request starts, so keep focus in the box.
    inputRef.current?.focus();
  }

  function changePersona(next: SiteAssistantPersona | null) {
    setPersona(next);
    if (!ask.isPending) ask.reset();
  }

  function reset() {
    ask.reset();
    setQuestion("");
    inputRef.current?.focus();
  }

  const answer = ask.data;
  const asked = ask.variables;
  // Server citation URLs are site paths; anything else is dropped rather than linked.
  const citations = answer?.citations.filter((c) => isSitePath(c.url)) ?? [];
  const showCounter = question.length >= maxQuestionChars * COUNTER_THRESHOLD;

  return (
    <>
      <PersonaToggle persona={persona} onChange={changePersona} />

      <div className="grid w-full min-w-0 max-w-[660px] gap-3.5 rounded-2xl bg-white p-[18px] text-left card-shadow-lg sm:px-6 sm:py-[22px]">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-brand-slate">
          <span aria-hidden="true" className="h-[7px] w-[7px] flex-none rounded-full bg-brand-teal" />
          Ask about Open Grant Flow
        </h2>

        <form onSubmit={handleSubmit} className="flex min-w-0 flex-col gap-2.5 min-[481px]:flex-row">
          <label htmlFor="site-assistant-question" className="sr-only">
            Ask a question about Open Grant Flow
          </label>
          <input
            ref={inputRef}
            id="site-assistant-question"
            type="text"
            autoComplete="off"
            maxLength={maxQuestionChars}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. We already use Fluxx. Why would we need this?"
            className="min-h-[46px] min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-brand-slate input-focus"
          />
          <button
            type="submit"
            disabled={ask.isPending || !question.trim()}
            className="min-h-10 rounded-lg bg-brand-navy px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {ask.isPending ? "Asking…" : "Ask"}
          </button>
        </form>
        {showCounter && (
          <p className="-mt-2 text-right text-xs text-slate-500">
            {question.length}/{maxQuestionChars}
          </p>
        )}

        {ask.isIdle && (
          <SuggestedQuestions
            questions={assistantSuggestions[persona ?? "default"]}
            onPick={pickSuggestion}
          />
        )}

        <div aria-live="polite" className="empty:hidden">
          {ask.isPending && (
            <p className="text-sm text-slate-500">Looking through the site…</p>
          )}
          {ask.isError && (
            <FallbackBlock
              message={FALLBACK_MESSAGES[classifySiteAssistantError(ask.error)]}
              onReset={reset}
            />
          )}
          {answer && !answer.answerable && (
            <FallbackBlock message={FALLBACK_MESSAGES.unanswerable} onReset={reset} />
          )}
          {answer?.answerable && asked && (
            <AnswerBlock
              question={asked.question}
              persona={asked.persona}
              answer={answer.answer}
              citations={citations}
              onReset={reset}
            />
          )}
        </div>

        <p className="text-xs text-slate-500">
          Questions are sent to an AI provider to generate an answer from this website&apos;s
          content, and are not stored by us. Please don&apos;t include personal details. See our{" "}
          <Link to="/legal#privacy-processors" className="underline hover:opacity-70">
            privacy policy
          </Link>
          .
        </p>
      </div>
    </>
  );
}
