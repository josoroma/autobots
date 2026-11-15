import { FileText, Paperclip, X } from "lucide-react";

import type { Attachments } from "@/components/composer/use-attachments";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/field";
import {
  ACCEPTED_FILES,
  type Attached,
  fileSize,
  MAX_FILES,
} from "@/lib/attachments";

/** One attached file as a chip: its name, type and size (PRD-Studio HM-02), and Remove. */
function FileChip({
  file,
  held,
  onRemove,
}: {
  file: Attached;
  held: boolean;
  onRemove: () => void;
}) {
  return (
    <li
      data-attached={file.path}
      className="bg-background flex max-w-full min-w-0 items-center gap-2.5 rounded-lg border py-1.5 pr-1.5 pl-2 text-ui"
    >
      <span
        aria-hidden="true"
        className="text-muted-foreground grid size-7 shrink-0 place-items-center rounded-md border"
      >
        <FileText className="size-3.5" />
      </span>
      <span className="flex min-w-0 flex-col">
        <span data-field="file-name" className="truncate font-medium">
          {file.name}
        </span>
        <span className="text-muted-foreground truncate text-tag">
          <span data-field="file-type">{file.media_type}</span>
          {" · "}
          <span data-field="file-size" className="tabular-nums">
            {fileSize(file.size)}
          </span>
        </span>
      </span>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="size-7 shrink-0"
        aria-label={`Remove ${file.name}`}
        disabled={held}
        onClick={onRemove}
      >
        <X aria-hidden="true" className="size-3.5" />
      </Button>
    </li>
  );
}

/**
 * The file input, the attached files and why any weren't attached (PRD-Tool-Catalog FI-01). While a
 * request is held, the files stay as they were sent (Decision 0027 D2).
 */
export function AttachmentField({
  attachments,
  held,
}: {
  attachments: Attachments;
  held: boolean;
}) {
  return (
    <div
      className="flex flex-col gap-2 border-t px-5 pt-4"
      data-field="attachments"
    >
      <Label htmlFor="attachments" className="flex items-center gap-2">
        <Paperclip
          aria-hidden="true"
          className="text-muted-foreground size-4"
        />
        Attach files
      </Label>
      <Input
        id="attachments"
        type="file"
        multiple
        accept={ACCEPTED_FILES}
        aria-describedby="attachments-help"
        disabled={held}
        className="min-w-0 file:mr-3 file:border-0 file:bg-transparent file:font-medium"
        onChange={(event) => {
          void attachments.attach(event.target.files);
          event.target.value = "";
        }}
      />
      <p id="attachments-help" className="text-muted-foreground text-xs">
        Up to {MAX_FILES} plain text, markdown, JSON or CSV files, 1 MiB each.
        The run can read them under inputs/.
      </p>
      {attachments.files.length === 0 ? null : (
        <ul className="flex flex-wrap gap-2 pt-1" aria-label="Attached files">
          {attachments.files.map((file) => (
            <FileChip
              key={file.path}
              file={file}
              held={held}
              onRemove={() => attachments.remove(file.path)}
            />
          ))}
        </ul>
      )}
      <div aria-live="polite" data-field="attach-refusals">
        {attachments.errors.map((reason) => (
          <p key={reason} className="text-sm">
            {reason}
          </p>
        ))}
      </div>
    </div>
  );
}
