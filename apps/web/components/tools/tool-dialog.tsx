import Link from "next/link";

import { ToolDetail } from "@/components/tools/tool-detail";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";

/**
 * The detail in a native modal dialog, open while the URL names the tool (?tool=). Escape, Close and a
 * click outside close it, and focus returns through `returnFocus` (Decision 0026 G2, G3). The tool's
 * title names the dialog once it loads, and its ID until then (WTAP-13).
 */
export function ToolDialog({
  toolId,
  onClosed,
  returnFocus,
}: {
  toolId: string;
  onClosed: () => void;
  returnFocus: () => HTMLElement | null;
}) {
  return (
    <Dialog
      open
      onClose={onClosed}
      returnFocus={returnFocus}
      surface="page"
      size="3xl"
      data-panel={toolId}
      aria-labelledby="tool-heading"
      aria-label={toolId}
      className="max-h-[min(92vh,60rem)] overflow-y-auto overscroll-contain p-0"
    >
      <div className="space-y-3 p-5 sm:p-6">
        <div className="flex items-center gap-3 text-ui">
          <Link
            href={`/tools/${encodeURIComponent(toolId)}`}
            className="underline underline-offset-4"
          >
            Open as a page
          </Link>
          <form method="dialog" className="ml-auto">
            <Button type="submit" variant="outline" size="sm">
              Close
            </Button>
          </form>
        </div>
        <ToolDetail toolId={toolId} />
      </div>
    </Dialog>
  );
}
