/**
 * The files attached to the next run (PRD-Tool-Catalog FI-01), admitted by lib/attachments. Nothing
 * is sent until Run is pressed, and the files go with that one request. Each change lands on the
 * files kept when it's applied, so two file choices that overlap while their texts are read both
 * keep their files.
 */
import { useState } from "react";

import {
  admitChecked,
  checkFiles,
  type Attached,
  type FileAdmission,
  MAX_FILES,
} from "@/lib/attachments";

export interface Attachments {
  files: readonly Attached[];
  /** Why each file of the last choice wasn't attached. */
  errors: readonly string[];
  attach: (chosen: FileList | null) => Promise<void>;
  remove: (path: string) => void;
  /** Forgets the files and errors, once a run has taken the files. */
  clear: () => void;
}

const NONE: FileAdmission = { files: [], errors: [] };

export function useAttachments(): Attachments {
  const [admission, setAdmission] = useState<FileAdmission>(NONE);

  async function attach(chosen: FileList | null): Promise<void> {
    // At most MAX_FILES texts are read, which is all one choice can add. The count is checked as
    // the choice lands.
    const checked = await checkFiles(Array.from(chosen ?? []), MAX_FILES);
    setAdmission((current) => admitChecked(current.files, checked));
  }

  return {
    files: admission.files,
    errors: admission.errors,
    attach,
    remove: (path) =>
      setAdmission((current) => ({
        ...current,
        files: current.files.filter((file) => file.path !== path),
      })),
    clear: () => setAdmission(NONE),
  };
}
