import Link from "next/link";
import { useEffect, useRef } from "react";

import { ToolDetail } from "@/components/tools/tool-detail";
import { Button } from "@/components/ui/button";

/**
 * The detail in a native modal dialog, which makes the page behind it inert and traps focus. Escape,
 * Close and a click on the backdrop close it, and the URL keeps ?tool= (Decision 0026 G2, G3).
 */
export function ToolDialog({
  toolId,
  onClosed,
}: {
  toolId: string;
  onClosed: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const element = dialog.current;
    if (element !== null && !element.open) element.showModal();
  }, []);
  return (
    <dialog
      ref={dialog}
      data-panel={toolId}
      aria-labelledby="tool-heading"
      onClose={onClosed}
      onClick={(event) => {
        // The content fills the dialog's box, so a click on the dialog itself is the backdrop.
        if (event.target === event.currentTarget) event.currentTarget.close();
      }}
      className="bg-background text-foreground border-border m-auto max-h-[min(92vh,60rem)] w-[calc(100%-2rem)] max-w-3xl overflow-y-auto overscroll-contain rounded-2xl border p-0 shadow-lg backdrop:bg-black/60"
    >
      <div className="space-y-3 p-5 sm:p-6">
        <div className="flex items-center gap-3 text-[13px]">
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
    </dialog>
  );
}
