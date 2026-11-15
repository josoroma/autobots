import type { Metadata } from "next";

import { PageHeader } from "@/components/ui/page-header";
import { SHORTCUTS } from "@/lib/shortcuts";

export const metadata: Metadata = { title: "Keyboard" };

// PRD-Studio SE-07: each shortcut the app offers, with its keys and what it does.
export default function KeyboardPage() {
  return (
    <div className="max-w-3xl space-y-6">
      <PageHeader title="Keyboard" />
      {SHORTCUTS.map((group) => (
        <section
          key={group.where}
          aria-labelledby={`keys-${group.where.toLowerCase().replaceAll(" ", "-")}`}
          className="border-border space-y-2 border-t pt-5"
        >
          <h2
            id={`keys-${group.where.toLowerCase().replaceAll(" ", "-")}`}
            className="text-sm font-semibold"
          >
            {group.where}
          </h2>
          <dl data-field="shortcuts" className="divide-border divide-y text-sm">
            {group.shortcuts.map((shortcut) => (
              <div
                key={shortcut.action}
                data-shortcut={shortcut.keys.join("+")}
                className="grid gap-1 py-2.5 sm:grid-cols-[9rem_minmax(0,1fr)] sm:gap-4"
              >
                <dt className="flex flex-wrap items-center gap-1">
                  {shortcut.keys.map((key) => (
                    <kbd
                      key={key}
                      className="border-border bg-muted min-w-6 rounded-md border px-1.5 py-0.5 text-center font-mono text-caption"
                    >
                      {key}
                    </kbd>
                  ))}
                </dt>
                <dd>{shortcut.action}</dd>
              </div>
            ))}
          </dl>
        </section>
      ))}
    </div>
  );
}
