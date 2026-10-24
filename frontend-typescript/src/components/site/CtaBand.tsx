import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { SiteWrap } from "./SiteSection";

export function CtaBand({ id, title, body, cta }: {
  id?: string;
  title: string;
  body?: ReactNode;
  cta: { label: string; to: string };
}) {
  return (
    <section id={id} className="bg-brand-navy py-16 text-white">
      <SiteWrap className="flex flex-wrap items-center justify-between gap-x-10 gap-y-6">
        <div>
          <h2 className="text-site-h2 max-w-[24ch] text-white">{title}</h2>
          {body && <div className="mt-2.5 max-w-[44ch] text-[#c3d2e2]">{body}</div>}
        </div>
        <Link
          to={cta.to}
          className="inline-flex min-h-12 items-center rounded-lg bg-white px-6 py-3 font-medium text-brand-navy transition-opacity hover:opacity-90"
        >
          {cta.label}
        </Link>
      </SiteWrap>
    </section>
  );
}
