import { AppearanceControl } from "@/components/appearance-control";
import { PageHeader } from "@/components/ui/page-header";

// Decision 0021: one settings section, a label column on the left and its control on the right. PRD-Studio
// SE-03 (Decision 0022) adds System, serif documents, density and reduced motion to Appearance.
export default function SettingsPage() {
  return (
    <div className="max-w-3xl space-y-8">
      <PageHeader title="Settings" />
      <section
        aria-labelledby="appearance-heading"
        className="border-border grid gap-4 border-t pt-5 md:grid-cols-[minmax(0,240px)_minmax(0,1fr)] md:gap-7"
      >
        <div className="space-y-1">
          <h2 id="appearance-heading" className="text-sm font-semibold">
            Appearance
          </h2>
          <p className="text-muted-foreground text-[12.5px] leading-relaxed">
            These choices are stored in this browser. They change presentation
            only, never a run, an approval or a workflow.
          </p>
        </div>
        <AppearanceControl />
      </section>
    </div>
  );
}
