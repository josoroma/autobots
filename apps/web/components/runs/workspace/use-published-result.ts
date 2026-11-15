/**
 * The run's stored result: the newest published artifact's text, which replaces any live text
 * (US-15.24). A newer artifact aborts the read of an older one, and a result already shown stays
 * until the newer one is read.
 */
import { useEffect, useState } from "react";

import { readStoredText } from "@/lib/runs/published-result";

export interface StoredResult {
  id: string;
  name: string;
  text: string;
}

export function usePublishedResult(
  published: { id: string; name: string } | null,
): StoredResult | null {
  const [result, setResult] = useState<StoredResult | null>(null);
  const id = published?.id ?? null;
  const name = published?.name ?? "";
  useEffect(() => {
    if (id === null) return;
    const controller = new AbortController();
    void readStoredText(id, { signal: controller.signal }).then((text) => {
      if (text !== null && !controller.signal.aborted)
        setResult({ id, name, text });
    });
    return () => controller.abort();
  }, [id, name]);
  return result;
}
