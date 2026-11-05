import { AboutServices } from "@/components/about-services";
import { ServiceStatusBadge } from "@/components/service-status-badge";
import { Card } from "@/components/ui/card";
import { fetchServiceStatus } from "@/lib/service-status";

// The status is read per request, on the server, so it is never baked into a build.
export const dynamic = "force-dynamic";

export default async function HomePage() {
  const status = await fetchServiceStatus();
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Local workbench</h1>
      <Card aria-labelledby="services-heading" className="space-y-3">
        <h2 id="services-heading" className="text-lg font-medium">
          Services
        </h2>
        <p className="text-muted-foreground text-sm">
          Everything runs on this Mac. Inference is not configured yet, and this
          page calls no model.
        </p>
        <ServiceStatusBadge status={status} />
        <AboutServices />
      </Card>
    </div>
  );
}
