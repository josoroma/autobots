"use client";

import { parseSearchResults, type SearchResults } from "@autobots/api-client";
import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useId, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/field";
import { useMismatchLog } from "@/components/ui/load-state";
import { typing } from "@/lib/keyboard";
import { failureWords, worstFailure, type LoadFailure } from "@/lib/load";
import { useResource, type Resource } from "@/lib/use-resource";
import { cn } from "@/lib/utils";

type Result = SearchResults["results"][number];

const WHAT = "search results";

const KIND: Record<Result["kind"], string> = {
  run: "Run",
  expert: "Expert",
  workflow: "Workflow",
  tool: "Tool",
};

// PRD-Studio SR-01 and Decision 0022 D3: ⌘K, or the button after the skip link, opens one search over
// this workspace. The palette is a modal dialog: a combobox over a listbox, arrows to move, Enter to
// open, Escape to close, and focus goes back to where it was.
export function SearchPalette() {
  const router = useRouter();
  const dialog = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const listId = useId();
  const [query, setQuery] = useState("");
  const term = query.trim();
  // Typing sends one read once it pauses. A failed search says why, never that nothing matches (WCMP-05).
  const search = useResource(
    term === "" ? null : `/api/v1/search?q=${encodeURIComponent(term)}`,
    parseSearchResults,
    { delayMs: 150 },
  );
  useMismatchLog(search.state);
  // The highlighted option, for the read it was chosen in. A newer read starts at the first.
  const [chosen, setChosen] = useState({ read: 0, index: 0 });
  const active = chosen.read === search.settled ? chosen.index : 0;
  const setActive = (index: number) =>
    setChosen({ read: search.settled, index });
  const { reload, clear } = search;

  const open = useCallback(() => {
    if (dialog.current?.open) return;
    opener.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    setQuery("");
    // Nothing from an earlier search shows, so the same words typed again read again.
    clear();
    setChosen({ read: -1, index: 0 });
    dialog.current?.showModal();
    input.current?.focus();
  }, [clear]);

  useEffect(() => {
    function onKey(event: KeyboardEvent): void {
      if (
        (event.metaKey || event.ctrlKey) &&
        !event.altKey &&
        event.key.toLowerCase() === "k" &&
        !typing(event.target)
      ) {
        event.preventDefault();
        open();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  function go(result: Result | undefined): void {
    if (result === undefined) return;
    opener.current = null;
    dialog.current?.close();
    router.push(result.href);
  }

  function restoreFocus(): void {
    opener.current?.focus();
    opener.current = null;
  }

  const shown: Result[] =
    search.state.kind === "ready" ? search.state.value.results : [];
  const failure = worstFailure([search.state]);
  const optionId = (index: number) => `${listId}-option-${index}`;
  return (
    <>
      <button
        type="button"
        onClick={open}
        aria-keyshortcuts="Meta+K Control+K"
        data-field="search-button"
        className="text-sidebar-foreground/80 hover:bg-sidebar-accent border-sidebar-border flex w-full items-center gap-2 rounded-lg border px-2.5 py-1.5 text-[13px]"
      >
        <Search aria-hidden="true" className="size-3.5 shrink-0" />
        <span className="flex-1 text-left">Search</span>
        <kbd
          aria-hidden="true"
          className="text-muted-foreground border-sidebar-border rounded border px-1 font-mono text-[11px]"
        >
          ⌘K
        </kbd>
      </button>
      <dialog
        ref={dialog}
        aria-label="Search"
        onClose={restoreFocus}
        className="bg-popover text-popover-foreground border-border mx-auto mt-[12vh] w-[calc(100%-2rem)] max-w-xl rounded-2xl border p-0 shadow-lg backdrop:bg-black/50"
      >
        <div className="border-border flex items-center gap-2.5 border-b px-4 py-3">
          <Search
            aria-hidden="true"
            className="text-muted-foreground size-4 shrink-0"
          />
          <Input
            ref={input}
            role="combobox"
            aria-label="Search this workspace"
            aria-expanded={shown.length > 0}
            aria-controls={listId}
            aria-autocomplete="list"
            aria-activedescendant={
              shown.length > 0 ? optionId(active) : undefined
            }
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                event.preventDefault();
                if (shown.length === 0) return;
                const step = event.key === "ArrowDown" ? 1 : -1;
                setActive((active + step + shown.length) % shown.length);
              } else if (event.key === "Enter") {
                event.preventDefault();
                go(shown[active]);
              }
            }}
            placeholder="Search runs, Experts, workflows and tools"
            className="placeholder:text-muted-foreground h-auto min-w-0 flex-1 border-0 bg-transparent px-0 py-1 text-[15px] dark:bg-transparent"
          />
        </div>
        <ul
          id={listId}
          role="listbox"
          aria-label="Results"
          data-field="search-results"
          className="max-h-[50vh] overflow-y-auto p-1.5"
        >
          {shown.map((result, index) => (
            <li
              key={`${result.kind}-${result.id}`}
              id={optionId(index)}
              role="option"
              aria-selected={index === active}
              data-kind={result.kind}
              onMouseEnter={() => setActive(index)}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => go(result)}
              className={cn(
                "flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-[13.5px]",
                index === active && "bg-accent text-accent-foreground",
              )}
            >
              <span className="text-muted-foreground w-16 shrink-0 text-[12px]">
                {KIND[result.kind]}
              </span>
              <span className="min-w-0 flex-1 truncate">{result.title}</span>
              {result.detail === null ? null : (
                <span className="text-muted-foreground shrink-0 font-mono text-[11.5px]">
                  {result.detail.replaceAll("_", " ")}
                </span>
              )}
            </li>
          ))}
        </ul>
        <div className="border-border flex items-center gap-3 border-t px-4 py-2">
          <p
            role="status"
            data-field="search-status"
            data-reason={failure?.kind}
            className="text-muted-foreground flex-1 text-[12px]"
          >
            {statusLine(search, failure, shown.length)}
          </p>
          {failure !== null && failureWords(failure, WHAT).retry ? (
            <Button
              variant="outline"
              size="sm"
              disabled={search.pending}
              onClick={reload}
            >
              Retry
            </Button>
          ) : null}
        </div>
      </dialog>
    </>
  );
}

function statusLine(
  search: Resource<SearchResults>,
  failure: LoadFailure | null,
  count: number,
): string {
  if (search.state.kind === "idle") {
    return "Type to search. ↑ ↓ to move, ↵ to open, Esc to close.";
  }
  if (search.pending || search.state.kind === "loading") return "Searching.";
  if (failure !== null) return failureWords(failure, WHAT).words;
  return count === 0
    ? "Nothing in this workspace matches."
    : `${count} ${count === 1 ? "result" : "results"}.`;
}
