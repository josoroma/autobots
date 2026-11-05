import { AppearanceControl } from "@/components/appearance-control";
import { Card } from "@/components/ui/card";

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Settings</h1>
      <Card aria-labelledby="appearance-heading" className="space-y-3">
        <h2 id="appearance-heading" className="text-lg font-medium">
          Appearance
        </h2>
        <p className="text-muted-foreground text-sm">
          This choice is stored in this browser. It changes presentation only.
        </p>
        <AppearanceControl />
      </Card>
    </div>
  );
}
