import type { ReactNode } from "react";

export function SiteWrap({ className = "", children }: {
  className?: string;
  children: ReactNode;
}) {
  return <div className={`mx-auto max-w-[1120px] px-4 sm:px-5 ${className}`}>{children}</div>;
}

export function SiteSection({ id, alt = false, className = "", children }: {
  id?: string;
  alt?: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section
      id={id}
      className={`py-14 md:py-[72px] ${alt ? "bg-brand-mist" : ""} ${className}`}
    >
      <SiteWrap>{children}</SiteWrap>
    </section>
  );
}
