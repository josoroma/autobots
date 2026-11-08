import type { ReactNode } from "react";

import { SettingsNav } from "@/components/settings-nav";

// PRD-Studio SE-02: one place for each preference and fact. The sections sit above the page, stacked,
// so Tab runs from them down into the page and never climbs back.
export default function SettingsLayout({ children }: { children: ReactNode }) {
  return (
    <div className="space-y-6">
      <SettingsNav />
      <div className="min-w-0">{children}</div>
    </div>
  );
}
