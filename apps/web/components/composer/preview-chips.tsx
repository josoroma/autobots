import type { RunPreview } from "@autobots/api-client";

function Chips({ preview }: { preview: RunPreview }) {
  return (
    <>
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-muted-foreground mr-1">Models</span>
        <ul className="flex flex-wrap gap-1.5" aria-label="Models">
          {preview.profiles.map((item) => (
            <li
              key={item.profile}
              data-preview-profile={item.profile}
              title={item.roles.join(", ")}
              className="border-border rounded-full border px-2.5 py-0.5"
            >
              {item.label} ·{" "}
              {item.roles.length === 1
                ? item.roles[0]
                : `${item.roles.length} roles`}
            </li>
          ))}
        </ul>
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-muted-foreground mr-1">Tools</span>
        <ul className="flex flex-wrap gap-1.5" aria-label="Tools">
          {preview.tools.map((tool) => (
            <li
              key={tool}
              data-preview-tool={tool}
              className="border-border rounded-full border px-2.5 py-0.5 font-mono text-[12px]"
            >
              {tool}
            </li>
          ))}
        </ul>
      </div>
    </>
  );
}

/**
 * The profiles the roles resolve to and the tools the run would be granted (PRD-Studio HM-03), or
 * that they're loading or can't be read.
 */
export function PreviewChips({
  preview,
  failed,
}: {
  preview: RunPreview | null;
  failed: boolean;
}) {
  return (
    <div data-field="preview" className="flex flex-col gap-2 text-[13px]">
      {failed ? (
        <p className="text-muted-foreground">
          What this run would use can&apos;t be read right now.
        </p>
      ) : preview === null ? (
        <p className="text-muted-foreground">Loading what it would use.</p>
      ) : (
        <Chips preview={preview} />
      )}
    </div>
  );
}
