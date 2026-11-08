import { AppearanceControl } from "@/components/appearance-control";
import { PageHeader } from "@/components/ui/page-header";

// Decision 0021: one settings section, a label column on the left and its control on the right. Only what
// exists is shown, so there's no sub-navigation and no density, motion or reading settings (R6).
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
            This choice is stored in this browser. It changes presentation only.
          </p>
        </div>
        <AppearanceControl />
      </section>
    </div>
  );
}
