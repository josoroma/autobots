"use client";

import {
  parseToolGrants,
  parseToolVersions,
  type ToolDescriptor,
} from "@autobots/api-client";
import { useState } from "react";

import { CopySchema } from "@/components/tools/copy-schema";
import { FieldTable } from "@/components/tools/field-table";
import { GrantedTo } from "@/components/tools/granted-to";
import {
  GrantableTo,
  RawSchema,
  ToolFacts,
  ToolGuide,
  ToolHeader,
} from "@/components/tools/tool-overview";
import { Card } from "@/components/ui/card";
import { Select } from "@/components/ui/field";
import { LoadState } from "@/components/ui/load-state";
import {
  keySource,
  OPERATION_CLASS_LABEL,
  PROVIDER_LABEL,
} from "@/lib/tools/text";
import { useResource } from "@/lib/use-resource";

/**
 * The tool's ID, the version shown, its provider, class and where its key comes from
 * (PRD-Tool-Catalog PK-05).
 */
function ToolIdentity({
  tool,
  versions,
  onChoose,
}: {
  tool: ToolDescriptor;
  versions: readonly ToolDescriptor[];
  onChoose: (version: number) => void;
}) {
  return (
    <dl className="grid grid-cols-[7rem_minmax(0,1fr)] items-center gap-x-3 gap-y-2.5 border-t pt-4 text-[13px]">
      <dt className="text-muted-foreground">ID</dt>
      <dd>
        <code className="border-border rounded-md border px-1.5 py-0.5 font-mono text-[12px]">
          {tool.tool_id}
        </code>
      </dd>
      <dt className="text-muted-foreground">Version</dt>
      <dd>
        <label className="sr-only" htmlFor="tool-version">
          Version
        </label>
        <Select
          id="tool-version"
          className="h-8 w-full max-w-40"
          value={tool.version}
          onChange={(event) => onChoose(Number(event.target.value))}
        >
          {versions.map((item) => (
            <option key={item.version} value={item.version}>
              Version {item.version}
            </option>
          ))}
        </Select>
      </dd>
      <dt className="text-muted-foreground">Provider</dt>
      <dd>{PROVIDER_LABEL[tool.provider]}</dd>
      <dt className="text-muted-foreground">Class</dt>
      <dd>{OPERATION_CLASS_LABEL[tool.operation_class]}</dd>
      <dt className="text-muted-foreground">Key</dt>
      <dd data-field="key" className="break-words">
        {keySource(tool) ?? "None"}
      </dd>
    </dl>
  );
}

/**
 * One tool's detail, on its page and in the Tools page's dialog (PRD-Tool-Catalog TS-01 to TS-03,
 * PRD-Studio TL-02, TL-03): any registered version, its guide, facts, grants, schema and fields.
 */
export function ToolDetail({ toolId }: { toolId: string }) {
  const { state, pending, reload } = useResource(
    `/api/v1/tools/${encodeURIComponent(toolId)}`,
    parseToolVersions,
  );
  // Who grants the tool needs only its ID, so it's read alongside its versions, not after them.
  const grants = useResource(
    `/api/v1/tools/${encodeURIComponent(toolId)}/grants`,
    parseToolGrants,
  );
  const [chosen, setChosen] = useState<number | null>(null);
  if (state.kind !== "ready") {
    return (
      <LoadState
        state={state}
        what="this tool"
        notFound="That tool isn't in the catalog."
        onRetry={reload}
        pending={pending}
      />
    );
  }
  const versions = state.value.versions;
  const newest = versions.at(-1);
  if (newest === undefined) return null;
  const tool = versions.find((item) => item.version === chosen) ?? newest;
  return (
    <div className="space-y-5">
      <Card aria-labelledby="tool-heading" className="space-y-5">
        <ToolHeader tool={tool} />
        <ToolGuide guide={tool.guide} />
        <ToolFacts tool={tool} />
        <ToolIdentity tool={tool} versions={versions} onChoose={setChosen} />
        <GrantableTo grantors={tool.grantable_to} />
      </Card>
      <GrantedTo toolId={tool.tool_id} grants={grants} />
      <CopySchema schema={tool.input_schema} version={tool.version} />
      <FieldTable
        direction="input"
        title="Inputs"
        caption={`Inputs of ${tool.title}`}
        fields={tool.fields.filter((field) => field.direction === "input")}
      />
      <FieldTable
        direction="output"
        title="Outputs"
        caption={`Outputs of ${tool.title}`}
        fields={tool.fields.filter((field) => field.direction === "output")}
      />
      <RawSchema tool={tool} />
    </div>
  );
}
