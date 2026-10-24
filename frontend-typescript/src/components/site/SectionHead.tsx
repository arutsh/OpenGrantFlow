import type { ReactNode } from "react";

export function SectionHead({ eyebrow, title, intro, as: Heading = "h2" }: {
  eyebrow?: string;
  title: string;
  intro?: ReactNode;
  as?: "h1" | "h2";
}) {
  return (
    <div className="mb-11 grid gap-3.5">
      {eyebrow && <p className="text-site-eyebrow">{eyebrow}</p>}
      <Heading
        className={`${Heading === "h1" ? "text-site-page-title" : "text-site-h2"} text-brand-slate`}
      >
        {title}
      </Heading>
      {intro && <div className="max-w-[65ch] text-slate-500">{intro}</div>}
    </div>
  );
}
