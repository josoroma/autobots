"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";

/** PRD-Studio TL-03: copies exactly the shown version's input schema. */
export function CopySchema({
  schema,
  version,
}: {
  schema: unknown;
  version: number;
}) {
  const [copied, setCopied] = useState<string | null>(null);
  async function copy(): Promise<void> {
    try {
      await navigator.clipboard.writeText(JSON.stringify(schema, null, 2));
      setCopied(`Copied the input schema of version ${version}.`);
    } catch {
      setCopied("Copying isn't allowed here.");
    }
  }
  return (
    <div className="flex items-center gap-3">
      <Button variant="outline" size="sm" onClick={() => void copy()}>
        Copy schema
      </Button>
      {copied === null ? null : (
        <p role="status" data-message="copied" className="text-ui">
          {copied}
        </p>
      )}
    </div>
  );
}
