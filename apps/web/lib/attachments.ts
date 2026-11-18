/**
 * The files the goal composer attaches as run inputs (PRD-Tool-Catalog FI-01): up to five plain
 * text, markdown, JSON or CSV files of at most 1 MiB, each under inputs/ with its media type. Nothing
 * is sent until Run is pressed, and the files go with that one request. Pure apart from reading a
 * chosen file's text, and JSX-free, so `node --test` covers it (WCMP-11).
 */
import type { InputDocument } from "@autobots/api-client";

export const MAX_FILES = 5;
export const MAX_FILE_BYTES = 1_048_576;

export type MediaType = NonNullable<InputDocument["media_type"]>;

const MEDIA_TYPES: Readonly<Record<string, MediaType>> = {
  txt: "text/plain",
  text: "text/plain",
  md: "text/markdown",
  markdown: "text/markdown",
  json: "application/json",
  csv: "text/csv",
};

/** The file input's accept list: the extensions and media types above. */
export const ACCEPTED_FILES =
  ".txt,.text,.md,.markdown,.json,.csv,text/plain,text/markdown,application/json,text/csv";

/** A kept file, as its chip shows it and as Run sends it. */
export interface Attached {
  name: string;
  path: string;
  media_type: MediaType;
  content: string;
  size: number;
}

/** A file a person chose: the browser's File, or a stand-in under test. */
export type ChosenFile = Pick<File, "name" | "size" | "text">;

/**
 * The files kept after a choice, and why each other file wasn't attached, in its own words rather
 * than as a run admission's refusal (WCMP-17).
 */
export interface FileAdmission {
  files: readonly Attached[];
  errors: readonly string[];
}

/** The media type a file's extension names, in any case, or undefined for any other file. */
export function mediaTypeOf(name: string): MediaType | undefined {
  const extension = name.split(".").pop()?.toLowerCase() ?? "";
  return Object.hasOwn(MEDIA_TYPES, extension)
    ? MEDIA_TYPES[extension]
    : undefined;
}

/**
 * The file's path under inputs/: safe characters only, no leading dot or dash, at most 180
 * characters, and numbered from 2 when the path is taken.
 */
export function inputPath(name: string, taken: readonly Attached[]): string {
  const base =
    name.replace(/[^A-Za-z0-9._-]/g, "-").replace(/^[.-]+/, "") || "file";
  let candidate = `inputs/${base.slice(0, 180)}`;
  for (
    let count = 2;
    taken.some((file) => file.path === candidate);
    count += 1
  ) {
    candidate = `inputs/${count}-${base.slice(0, 176)}`;
  }
  return candidate;
}

/**
 * A chosen file after the checks that need no kept files: read, with its text; refused for its type
 * or size; or past `room`, so never read.
 */
export type CheckedFile =
  | {
      kind: "read";
      name: string;
      media_type: MediaType;
      content: string;
      size: number;
    }
  | { kind: "refused"; name: string; error: string }
  | { kind: "no_room"; name: string };

/**
 * Each chosen file's type and size checked in order, and the text read of at most `room` files that
 * pass, so a file refused for its type or size, or past the room, is never read. The count is
 * checked by `admitChecked`, against the files kept when the choice lands.
 */
export async function checkFiles(
  chosen: readonly ChosenFile[],
  room: number,
): Promise<CheckedFile[]> {
  const checked: CheckedFile[] = [];
  let read = 0;
  for (const file of chosen) {
    const mediaType = mediaTypeOf(file.name);
    if (mediaType === undefined) {
      checked.push({
        kind: "refused",
        name: file.name,
        error: `${file.name}: only plain text, markdown, JSON or CSV can be attached.`,
      });
    } else if (file.size > MAX_FILE_BYTES) {
      checked.push({
        kind: "refused",
        name: file.name,
        error: `${file.name}: a file can be at most 1 MiB.`,
      });
    } else if (read >= room) {
      checked.push({ kind: "no_room", name: file.name });
    } else {
      read += 1;
      checked.push({
        kind: "read",
        name: file.name,
        media_type: mediaType,
        content: await file.text(),
        size: file.size,
      });
    }
  }
  return checked;
}

/**
 * The kept files, then each checked file in order unless it is past the fifth, of another type or
 * over 1 MiB, checked in that order. A file left unread for want of room is past the fifth. Pure, so
 * a choice can land on whatever files are kept by then.
 */
export function admitChecked(
  kept: readonly Attached[],
  checked: readonly CheckedFile[],
): FileAdmission {
  const files = [...kept];
  const errors: string[] = [];
  for (const file of checked) {
    if (files.length >= MAX_FILES || file.kind === "no_room") {
      errors.push(`${file.name}: only ${MAX_FILES} files can be attached.`);
    } else if (file.kind === "refused") {
      errors.push(file.error);
    } else {
      files.push({
        name: file.name,
        path: inputPath(file.name, files),
        media_type: file.media_type,
        content: file.content,
        size: file.size,
      });
    }
  }
  return { files, errors };
}

/**
 * The kept files, then each chosen file in order unless it is past the fifth, of another type or
 * over 1 MiB, checked in that order. Only an attached file's text is read.
 */
export async function admitFiles(
  kept: readonly Attached[],
  chosen: readonly ChosenFile[],
): Promise<FileAdmission> {
  return admitChecked(
    kept,
    await checkFiles(chosen, Math.max(0, MAX_FILES - kept.length)),
  );
}

/** A file chip's size in bytes, KB or MB (PRD-Studio HM-02). */
export function fileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1_048_576).toFixed(1)} MB`;
}
