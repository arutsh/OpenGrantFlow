import type { ReactNode } from "react";

export function Callout({ id, className = "", children }: {
  id?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div
      id={id}
      className={`max-w-[78ch] rounded-xl border border-brand-teal-tint-border bg-brand-teal-tint px-[22px] py-[18px] text-brand-slate ${className}`}
    >
      {children}
    </div>
  );
}
