import type { ToolDescriptor } from "@autobots/api-client";
import type { ReactNode } from "react";

import { CopySchema } from "@/components/tools/copy-schema";
import { FieldTable } from "@/components/tools/field-table";
import {
  GrantableTo,
  RawSchema,
  ToolFacts,
  ToolGuide,
  ToolHeader,
} from "@/components/tools/tool-overview";
import { Card } from "@/components/ui/card";
import {
  keySource,
  OPERATION_CLASS_LABEL,
  PROVIDER_LABEL,
} from "@/lib/tools/text";

/**
 * The tool's ID, the version shown, its provider, class and where its key comes from
 * (PRD-Tool-Catalog PK-05). `version` is the control that chooses the version.
 */
function ToolIdentity({
  tool,
  version,
}: {
  tool: ToolDescriptor;
  version: ReactNode;
}) {
  return (
    <dl className="grid grid-cols-[7rem_minmax(0,1fr)] items-center gap-x-3 gap-y-2.5 border-t pt-4 text-ui">
      <dt className="text-muted-foreground">ID</dt>
      <dd>
        <code className="border-border rounded-md border px-1.5 py-0.5 font-mono text-caption">
          {tool.tool_id}
        </code>
      </dd>
      <dt className="text-muted-foreground">Version</dt>
      <dd>{version}</dd>
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
 * One version of a tool (PRD-Tool-Catalog TS-01 to TS-03, PRD-Studio TL-02, TL-03): its guide, facts,
 * grants, schema and fields. It holds no state, so the tool's page renders it on the server (R-67)
 * and the Tools page's dialog in the browser; each passes its own version control and grants.
 */
export function ToolDetailBody({
  tool,
  version,
  grants,
}: {
  tool: ToolDescriptor;
  version: ReactNode;
  grants: ReactNode;
}) {
  return (
    <div className="space-y-5">
      <Card aria-labelledby="tool-heading" className="space-y-5">
        <ToolHeader tool={tool} />
        <ToolGuide guide={tool.guide} />
        <ToolFacts tool={tool} />
        <ToolIdentity tool={tool} version={version} />
        <GrantableTo grantors={tool.grantable_to} />
      </Card>
      {grants}
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
