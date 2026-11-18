/**
 * Pins which files the goal composer attaches as run inputs, and the paths and sizes it shows
 * (PRD-Tool-Catalog FI-01, PRD-Studio HM-02, WCMP-11).
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  admitChecked,
  admitFiles,
  type Attached,
  checkFiles,
  type ChosenFile,
  type FileAdmission,
  fileSize,
  inputPath,
  MAX_FILE_BYTES,
  MAX_FILES,
  mediaTypeOf,
} from "../../lib/attachments.ts";

function chosen(name: string, content = "text", size?: number): ChosenFile {
  return {
    name,
    size: size ?? new TextEncoder().encode(content).length,
    text: () => Promise.resolve(content),
  };
}

function attached(path: string): Attached {
  return {
    name: path.slice("inputs/".length),
    path,
    media_type: "text/plain",
    content: "",
    size: 0,
  };
}

test("FI-01's limits are five files of at most 1 MiB", () => {
  assert.equal(MAX_FILES, 5);
  assert.equal(MAX_FILE_BYTES, 1_048_576);
});

test("plain text, markdown, JSON and CSV are known by extension, in any case", () => {
  assert.equal(mediaTypeOf("notes.txt"), "text/plain");
  assert.equal(mediaTypeOf("notes.TEXT"), "text/plain");
  assert.equal(mediaTypeOf("readme.md"), "text/markdown");
  assert.equal(mediaTypeOf("readme.Markdown"), "text/markdown");
  assert.equal(mediaTypeOf("data.json"), "application/json");
  assert.equal(mediaTypeOf("rates.CSV"), "text/csv");
  assert.equal(mediaTypeOf("archive.tar.csv"), "text/csv");
});

test("other extensions, and names that only match an object's own keys, aren't attached", () => {
  assert.equal(mediaTypeOf("photo.png"), undefined);
  assert.equal(mediaTypeOf("notes.txt.exe"), undefined);
  assert.equal(mediaTypeOf("Makefile"), undefined);
  assert.equal(mediaTypeOf("x.constructor"), undefined);
  assert.equal(mediaTypeOf("x.__proto__"), undefined);
});

test("chosen files are kept in order, with their type, size, content and a path under inputs/", async () => {
  const admitted = await admitFiles(
    [],
    [chosen("notes.txt", "plain notes"), chosen("rates.csv", "a,b")],
  );
  assert.deepEqual(admitted, {
    files: [
      {
        name: "notes.txt",
        path: "inputs/notes.txt",
        media_type: "text/plain",
        content: "plain notes",
        size: 11,
      },
      {
        name: "rates.csv",
        path: "inputs/rates.csv",
        media_type: "text/csv",
        content: "a,b",
        size: 3,
      },
    ],
    errors: [],
  });
});

test("a file past the fifth, of another type or over 1 MiB is refused with its reason", async () => {
  const kept = [1, 2, 3, 4].map((index) => attached(`inputs/${index}.txt`));
  const admitted = await admitFiles(kept, [
    chosen("photo.png"),
    chosen("big.json", "{}", MAX_FILE_BYTES + 1),
    chosen("fifth.md"),
    chosen("sixth.txt"),
    chosen("seventh.png"),
  ]);
  assert.deepEqual(
    admitted.files.map((file) => file.path),
    [...kept.map((file) => file.path), "inputs/fifth.md"],
  );
  // The count is checked first, so a sixth file of the wrong type says only five can be attached.
  assert.deepEqual(admitted.errors, [
    "photo.png: only plain text, markdown, JSON or CSV can be attached.",
    "big.json: a file can be at most 1 MiB.",
    "sixth.txt: only 5 files can be attached.",
    "seventh.png: only 5 files can be attached.",
  ]);
});

test("a file of exactly 1 MiB is attached, and a refused file's content is never read", async () => {
  let reads = 0;
  const counted = (file: ChosenFile): ChosenFile => ({
    ...file,
    text: () => {
      reads += 1;
      return file.text();
    },
  });
  const admitted = await admitFiles(
    [],
    [
      counted(chosen("edge.txt", "x", MAX_FILE_BYTES)),
      counted(chosen("over.txt", "x", MAX_FILE_BYTES + 1)),
      counted(chosen("photo.png")),
    ],
  );
  assert.deepEqual(
    admitted.files.map((file) => file.size),
    [MAX_FILE_BYTES],
  );
  assert.equal(reads, 1);
});

test("the files already kept stay as they were, ahead of the new ones", async () => {
  const kept = [attached("inputs/notes.txt")];
  const admitted = await admitFiles(kept, [chosen("notes.txt", "again")]);
  assert.equal(admitted.files[0], kept[0]);
  assert.equal(admitted.files[1]?.path, "inputs/2-notes.txt");
  assert.equal(kept.length, 1);
});

// The composer reads each choice's texts first, then lands it on the files kept by then, so a
// second choice made while the first is read keeps the first one's files (use-attachments.ts).
test("two choices read at once both keep their files, in the order they land", async () => {
  const first = await checkFiles([chosen("notes.txt", "one")], MAX_FILES);
  const second = await checkFiles(
    [chosen("notes.txt", "two"), chosen("rates.csv", "a,b")],
    MAX_FILES,
  );
  const none: FileAdmission = { files: [], errors: [] };
  const landed = [second, first].reduce(
    (current, checked) => admitChecked(current.files, checked),
    none,
  );
  assert.deepEqual(
    landed.files.map((file) => [file.path, file.content]),
    [
      ["inputs/notes.txt", "two"],
      ["inputs/rates.csv", "a,b"],
      ["inputs/2-notes.txt", "one"],
    ],
  );
  assert.deepEqual(landed.errors, []);
});

test("a choice that lands on files kept meanwhile still stops at five", async () => {
  const checked = await checkFiles(
    [chosen("a.txt"), chosen("b.txt"), chosen("c.png")],
    MAX_FILES,
  );
  const kept = [1, 2, 3, 4].map((index) => attached(`inputs/${index}.txt`));
  const admitted = admitChecked(kept, checked);
  assert.deepEqual(
    admitted.files.map((file) => file.path),
    [...kept.map((file) => file.path), "inputs/a.txt"],
  );
  assert.deepEqual(admitted.errors, [
    "b.txt: only 5 files can be attached.",
    "c.png: only 5 files can be attached.",
  ]);
});

test("no more texts are read than there is room for, and an unread file is past the fifth", async () => {
  let reads = 0;
  const counted = (name: string): ChosenFile => ({
    ...chosen(name),
    text: () => {
      reads += 1;
      return Promise.resolve("text");
    },
  });
  const kept = [1, 2, 3, 4].map((index) => attached(`inputs/${index}.txt`));
  const checked = await checkFiles(
    [counted("a.txt"), counted("photo.png"), counted("b.txt")],
    MAX_FILES - kept.length,
  );
  assert.equal(reads, 1);
  assert.deepEqual(
    checked.map((file) => file.kind),
    ["read", "refused", "no_room"],
  );
  assert.deepEqual(admitChecked(kept, checked).errors, [
    "photo.png: only 5 files can be attached.",
    "b.txt: only 5 files can be attached.",
  ]);
});

test("an input path keeps safe characters and drops leading dots and dashes", () => {
  assert.equal(inputPath("notes.txt", []), "inputs/notes.txt");
  assert.equal(inputPath("my notes (1).md", []), "inputs/my-notes--1-.md");
  assert.equal(inputPath("../../etc/passwd.txt", []), "inputs/etc-passwd.txt");
  assert.equal(inputPath(".hidden.json", []), "inputs/hidden.json");
  assert.equal(inputPath("-dash.csv", []), "inputs/dash.csv");
  assert.equal(inputPath("..", []), "inputs/file");
  assert.equal(inputPath("", []), "inputs/file");
});

test("a taken path is numbered from 2, and a number never reuses a taken one", () => {
  const taken = [attached("inputs/a.txt")];
  assert.equal(inputPath("a.txt", taken), "inputs/2-a.txt");
  assert.equal(
    inputPath("a.txt", [...taken, attached("inputs/2-a.txt")]),
    "inputs/3-a.txt",
  );
  // A name that sanitizes to a taken path is numbered too.
  assert.equal(
    inputPath("a?txt", [attached("inputs/a-txt")]),
    "inputs/2-a-txt",
  );
});

test("a long name is cut to 180 characters, and to 176 once numbered", () => {
  const long = `${"n".repeat(200)}.txt`;
  const first = inputPath(long, []);
  assert.equal(first, `inputs/${"n".repeat(180)}`);
  const second = inputPath(long, [attached(first)]);
  assert.equal(second, `inputs/2-${"n".repeat(176)}`);
});

test("a file's size reads in bytes, then KB, then MB, with one decimal", () => {
  assert.equal(fileSize(0), "0 B");
  assert.equal(fileSize(11), "11 B");
  assert.equal(fileSize(1023), "1023 B");
  assert.equal(fileSize(1024), "1.0 KB");
  assert.equal(fileSize(2048), "2.0 KB");
  assert.equal(fileSize(1_048_575), "1024.0 KB");
  assert.equal(fileSize(1_048_576), "1.0 MB");
});
