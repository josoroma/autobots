/**
 * One Expert's read (XWEB-05, WBLD-10), with its own loading and unavailable states. After a save,
 * the view the service returned is shown instead, until another Expert is opened.
 */
import { getExpert, type ExpertView } from "@autobots/api-client";
import { useState } from "react";

import { readOf } from "@/lib/load";
import { useResource, type Resource } from "@/lib/use-resource";

export interface ExpertRead {
  read: Resource<ExpertView>;
  /** The newest view, or null until it's read. */
  expert: ExpertView | null;
  saved: (view: ExpertView) => void;
}

export function useExpert(expertId: string): ExpertRead {
  const read = useResource(readOf(getExpert, expertId));
  const [written, setWritten] = useState<{
    expertId: string;
    view: ExpertView;
  } | null>(null);
  return {
    read,
    expert: written?.expertId === expertId ? written.view : read.value,
    saved: (view) => setWritten({ expertId, view }),
  };
}
