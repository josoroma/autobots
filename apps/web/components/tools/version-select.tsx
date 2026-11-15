"use client";

import { Select } from "@/components/ui/field";
import { useUrlDraft } from "@/lib/use-url-draft";
import { useUrlParams } from "@/lib/use-url-params";

/** PRD-Tool-Catalog TS-02: every registered version, by number. */
export function VersionSelect({
  value,
  versions,
  onChoose,
}: {
  value: number;
  /** The registered version numbers, oldest first. */
  versions: readonly number[];
  onChoose: (version: number) => void;
}) {
  return (
    <>
      <label className="sr-only" htmlFor="tool-version">
        Version
      </label>
      <Select
        id="tool-version"
        className="h-8 w-full max-w-40"
        value={value}
        onChange={(event) => onChoose(Number(event.target.value))}
      >
        {versions.map((version) => (
          <option key={version} value={version}>
            Version {version}
          </option>
        ))}
      </Select>
    </>
  );
}

/**
 * The tool page's version, kept in the URL as ?version=, so the page renders that version on the
 * server and a reload or a link keeps it (XWEB-13, R-67). The choice shows at once.
 */
export function PageVersionSelect({
  value,
  versions,
}: {
  value: number;
  versions: readonly number[];
}) {
  const url = useUrlParams();
  const chosen = useUrlDraft(String(value), (version) =>
    url.navigate("", { version }),
  );
  return (
    <VersionSelect
      value={Number(chosen.value)}
      versions={versions}
      onChoose={(version) => chosen.change(String(version))}
    />
  );
}
