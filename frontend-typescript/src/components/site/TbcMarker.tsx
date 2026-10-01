import type { ReactNode } from "react";

export function TbcMarker({ children }: { children: ReactNode }) {
  return (
    <div className="relative rounded-lg border-2 border-dashed border-amber-400 bg-amber-50 p-4">
      <span className="absolute -top-3 left-3 rounded bg-amber-400 px-2 py-0.5 text-xs font-semibold uppercase tracking-wide text-white">
        TBC
      </span>
      {children}
    </div>
  );
}
