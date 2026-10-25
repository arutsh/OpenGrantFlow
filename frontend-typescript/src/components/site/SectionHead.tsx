import type { ReactNode } from "react";

const VARIANTS = {
  h1: { wrap: "gap-[18px] [&>*]:max-w-[820px]", title: "text-site-page-title", intro: "text-site-lede grid gap-3 text-brand-slate" },
  h2: { wrap: "mb-11 gap-3.5", title: "text-site-h2", intro: "max-w-[65ch] text-slate-500" },
};

export function SectionHead({ eyebrow, title, intro, as: Heading = "h2" }: {
  eyebrow?: string;
  title: string;
  intro?: ReactNode;
  as?: "h1" | "h2";
}) {
  const variant = VARIANTS[Heading];
  return (
    <div className={`grid ${variant.wrap}`}>
      {eyebrow && <p className="text-site-eyebrow">{eyebrow}</p>}
      <Heading className={`${variant.title} text-brand-slate`}>{title}</Heading>
      {intro && <div className={variant.intro}>{intro}</div>}
    </div>
  );
}
