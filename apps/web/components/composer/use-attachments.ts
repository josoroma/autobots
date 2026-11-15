/**
 * The files attached to the next run (PRD-Tool-Catalog FI-01), admitted by lib/attachments. Nothing
 * is sent until Run is pressed, and the files go with that one request.
 */
import { useState } from "react";

import { admitFiles, type Attached } from "@/lib/attachments";

export interface Attachments {
  files: readonly Attached[];
  /** Why each file of the last choice wasn't attached. */
  errors: readonly string[];
  attach: (chosen: FileList | null) => Promise<void>;
  remove: (path: string) => void;
  /** Forgets the files and errors, once a run has taken the files. */
  clear: () => void;
}

export function useAttachments(): Attachments {
  const [files, setFiles] = useState<readonly Attached[]>([]);
  const [errors, setErrors] = useState<readonly string[]>([]);

  async function attach(chosen: FileList | null): Promise<void> {
    const admitted = await admitFiles(files, Array.from(chosen ?? []));
    setFiles(admitted.files);
    setErrors(admitted.errors);
  }

  return {
    files,
    errors,
    attach,
    remove: (path) => setFiles(files.filter((file) => file.path !== path)),
    clear: () => {
      setFiles([]);
      setErrors([]);
    },
  };
}
