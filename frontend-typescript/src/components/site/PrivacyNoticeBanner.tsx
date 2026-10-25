import { useLayoutEffect, useRef, useState } from "react";
import { privacyNotice, type PrivacyNotice } from "@/lib/privacyNotice";
import { isHiddenDraft } from "@/lib/siteContent";
import { SiteMarkdown } from "./SiteMarkdown";
import { TbcMarker } from "./TbcMarker";

export const DISMISSED_KEY = "ogf.privacyNotice.dismissed";

function readDismissedVersion(): string | null {
  try {
    return localStorage.getItem(DISMISSED_KEY);
  } catch {
    return null;
  }
}

function writeDismissedVersion(version: string) {
  try {
    localStorage.setItem(DISMISSED_KEY, version);
  } catch {
    // Storage blocked: the banner still hides for this page view via state.
  }
}

export function PrivacyNoticeBanner({
  notice = privacyNotice,
  isProd,
}: {
  notice?: PrivacyNotice;
  isProd?: boolean;
}) {
  const [dismissed, setDismissed] = useState(
    () => readDismissedVersion() === notice.version,
  );
  const barRef = useRef<HTMLDivElement>(null);
  const [barHeight, setBarHeight] = useState(0);
  const hiddenAsDraft = isHiddenDraft(notice.status, isProd);
  const visible = !dismissed && !hiddenAsDraft;

  useLayoutEffect(() => {
    const bar = barRef.current;
    if (!bar) return;
    const measure = () => setBarHeight(bar.offsetHeight);
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(measure);
    observer.observe(bar);
    return () => observer.disconnect();
  }, [visible]);

  if (!visible) return null;

  function dismiss() {
    writeDismissedVersion(notice.version);
    setDismissed(true);
  }

  const content = (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="text-xs leading-relaxed text-brand-slate sm:text-sm [&_a]:font-medium [&_a]:text-brand-teal [&_a]:underline">
        <SiteMarkdown>{notice.body}</SiteMarkdown>
      </div>
      <button
        type="button"
        onClick={dismiss}
        className="shrink-0 self-start rounded-lg bg-brand-navy px-4 py-1.5 text-sm font-medium text-white transition-opacity hover:opacity-90 sm:self-auto"
      >
        Got it
      </button>
    </div>
  );

  return (
    <>
      <div data-testid="privacy-notice-spacer" aria-hidden style={{ height: barHeight }} />
      <div
        ref={barRef}
        role="region"
        aria-label="Privacy notice"
        className="fixed inset-x-0 bottom-0 z-30 border-t border-slate-200 bg-white shadow-[0_-4px_12px_rgba(15,23,42,0.06)]"
      >
        <div className="mx-auto max-w-[1120px] px-4 py-3 sm:px-5">
          {notice.status === "draft" ? <TbcMarker>{content}</TbcMarker> : content}
        </div>
      </div>
    </>
  );
}
