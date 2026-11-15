import type { FieldDescriptor } from "@autobots/api-client";

import { Card } from "@/components/ui/card";
import { constraintText } from "@/lib/tools/text";

const COLUMNS = [
  "Field",
  "Type",
  "Required",
  "Constraints",
  "On run screens",
] as const;

/** One field: its path and description, type, whether required, constraints and visibility. */
function FieldRow({ field }: { field: FieldDescriptor }) {
  return (
    <tr
      data-field-path={field.path}
      className="border-b align-top last:border-b-0"
    >
      <th scope="row" className="py-2 pr-3 font-normal">
        <code className="font-mono text-[12.5px]">{field.path}</code>
        {field.description ? (
          <span className="text-muted-foreground block text-xs">
            {field.description}
          </span>
        ) : null}
      </th>
      <td className="py-2 pr-3">
        <code className="font-mono text-[12.5px]">{field.type}</code>
      </td>
      <td className="py-2 pr-3">{field.required ? "Required" : "Optional"}</td>
      <td className="py-2 pr-3">{constraintText(field.constraints)}</td>
      <td className="py-2 pr-3">{field.public ? "Shown" : "Not shown"}</td>
    </tr>
  );
}

/** A tool's inputs or outputs as a table, or None (WTAP-08). */
export function FieldTable({
  direction,
  title,
  caption,
  fields,
}: {
  direction: FieldDescriptor["direction"];
  title: string;
  caption: string;
  fields: readonly FieldDescriptor[];
}) {
  const id = `${direction}-heading`;
  return (
    <Card aria-labelledby={id} className="space-y-3">
      <h2 id={id} className="text-sm font-semibold">
        {title}
      </h2>
      {fields.length === 0 ? (
        <p className="text-muted-foreground text-sm">None.</p>
      ) : (
        // A scroll region a keyboard can reach and screen readers can name (axe
        // scrollable-region-focusable).
        <div
          tabIndex={0}
          role="region"
          aria-label={`${title} table`}
          className="overflow-x-auto"
        >
          <table
            className="w-full text-left text-[13px]"
            data-fields={direction}
          >
            <caption className="sr-only">{caption}</caption>
            <thead>
              <tr className="text-muted-foreground border-b text-xs">
                {COLUMNS.map((column) => (
                  <th
                    key={column}
                    scope="col"
                    className="pr-3 pb-2 font-medium"
                  >
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {fields.map((field) => (
                <FieldRow key={field.path} field={field} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
