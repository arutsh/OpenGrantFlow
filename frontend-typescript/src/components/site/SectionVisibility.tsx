import type { ReactNode } from "react";
import type { SiteSection } from "@/lib/siteContent";
import { TbcMarker } from "./TbcMarker";

export function SectionVisibility({ section, children }: {
  section: SiteSection | null;
  children: (section: SiteSection) => ReactNode;
}) {
  if (!section) return null;
  const content = children(section);
  return section.status === "draft" ? <TbcMarker>{content}</TbcMarker> : content;
}
