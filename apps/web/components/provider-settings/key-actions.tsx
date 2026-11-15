import type { ProviderStatus } from "@autobots/api-client";

import { Button } from "@/components/ui/button";

/**
 * Validate for any configured key, and Disconnect for one stored here, which never touches an
 * environment key.
 */
export function KeyActions({
  source,
  pending,
  onValidate,
  onDisconnect,
}: {
  source: ProviderStatus["source"];
  pending: boolean;
  onValidate: () => void;
  onDisconnect: () => void;
}) {
  const stored = source === "app";
  return (
    <>
      {source === "none" ? null : (
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" disabled={pending} onClick={onValidate}>
            Validate
          </Button>
          {stored ? (
            <Button variant="outline" disabled={pending} onClick={onDisconnect}>
              Disconnect
            </Button>
          ) : null}
        </div>
      )}
      {stored ? (
        <p className="text-muted-foreground max-w-2xl text-[12.5px] leading-relaxed">
          Disconnect removes this workspace&apos;s stored key. It does not touch
          an environment key. A request already sent may still finish.
        </p>
      ) : null}
    </>
  );
}
