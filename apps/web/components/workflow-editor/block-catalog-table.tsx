import { listWorkflowBlocks } from "@autobots/api-client";

import { Card } from "@/components/ui/card";
import { LoadState } from "@/components/ui/load-state";
import { SectionLabel } from "@/components/ui/page-header";
import { readOf } from "@/lib/load";
import { useResource } from "@/lib/use-resource";
import { cn } from "@/lib/utils";

const HEADER = "text-muted-foreground pb-2 text-xs font-medium";
const CELL = "text-muted-foreground py-2 font-mono text-[12px] wrap-anywhere";

/**
 * The blocks a graph can use, with their ports. Its read has its own loading and unavailable
 * states, with Retry, beside an editor that stays usable (WBLD-04).
 */
export function BlockCatalogTable({ className }: { className?: string }) {
  const catalog = useResource(readOf(listWorkflowBlocks));
  const { state } = catalog;
  return (
    <Card
      aria-labelledby="blocks-heading"
      className={cn("space-y-3", className)}
    >
      <SectionLabel id="blocks-heading">Blocks</SectionLabel>
      {state.kind !== "ready" ? (
        <LoadState
          state={state}
          what="the block catalog"
          onRetry={catalog.reload}
          pending={catalog.pending}
        />
      ) : (
        <table className="w-full text-left text-[13px]">
          <thead>
            <tr className="border-b">
              <th scope="col" className={cn(HEADER, "pr-2")}>
                Block
              </th>
              <th scope="col" className={cn(HEADER, "px-2")}>
                Inputs
              </th>
              <th scope="col" className={cn(HEADER, "pl-2")}>
                Outputs
              </th>
            </tr>
          </thead>
          <tbody>
            {state.value.blocks.map((block) => (
              <tr
                key={block.block}
                data-block={block.block}
                className="border-b align-top last:border-b-0"
              >
                <td className="py-2 pr-2 font-mono text-[12px] font-medium wrap-anywhere">
                  {block.block} v{block.version}
                </td>
                <td className={cn(CELL, "px-2")}>
                  {block.inputs.join(", ") || "none"}
                </td>
                <td className={cn(CELL, "pl-2")}>
                  {block.outputs.join(", ") || "none"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}
