import type { SearchResult } from "@autobots/api-client";

import { cn } from "@/lib/utils";

const KIND: Readonly<Record<SearchResult["kind"], string>> = {
  run: "Run",
  expert: "Expert",
  workflow: "Workflow",
  tool: "Tool",
};

/** The id of a result's option, which the combobox names as its active descendant. */
export function optionId(listId: string, index: number): string {
  return `${listId}-option-${index}`;
}

/** The results as a listbox. Focus stays in the combobox; hovering moves the highlight. */
export function SearchResults({
  listId,
  results,
  active,
  onHighlight,
  onOpen,
}: {
  listId: string;
  results: readonly SearchResult[];
  active: number;
  onHighlight: (index: number) => void;
  onOpen: (result: SearchResult) => void;
}) {
  return (
    <ul
      id={listId}
      role="listbox"
      aria-label="Results"
      data-field="search-results"
      className="max-h-[50vh] overflow-y-auto p-1.5"
    >
      {results.map((result, index) => (
        <li
          key={`${result.kind}-${result.id}`}
          id={optionId(listId, index)}
          role="option"
          aria-selected={index === active}
          data-kind={result.kind}
          onMouseEnter={() => onHighlight(index)}
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => onOpen(result)}
          className={cn(
            "flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-body",
            index === active && "bg-accent text-accent-foreground",
          )}
        >
          <span className="text-muted-foreground w-16 shrink-0 text-caption">
            {KIND[result.kind]}
          </span>
          <span className="min-w-0 flex-1 truncate">{result.title}</span>
          {result.detail === null ? null : (
            <span className="text-muted-foreground shrink-0 font-mono text-tag">
              {result.detail.replaceAll("_", " ")}
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}
