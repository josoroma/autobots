"use client";

import type { SearchResult } from "@autobots/api-client";
import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import {
  useCallback,
  useId,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";

import { optionId, SearchResults } from "@/components/search/search-results";
import { SearchStatus } from "@/components/search/search-status";
import { useSearch } from "@/components/search/use-search";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/field";
import { moveActive } from "@/lib/keyboard";
import { SEARCH_SHORTCUT } from "@/lib/shortcuts";
import { useShortcut } from "@/lib/use-shortcut";

// PRD-Studio SR-01 and Decision 0022 D3: ⌘K, or the button after the skip link, opens one search over
// this workspace. The palette is a modal dialog: a combobox over a listbox, arrows to move, Enter to
// open, Escape to close, and focus goes back to where it was.
export function SearchPalette() {
  const router = useRouter();
  const [shown, setShown] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const listId = useId();
  const [query, setQuery] = useState("");
  const search = useSearch(query);
  // The highlighted option, for the search it was chosen in. A newer search starts at the first.
  const [chosen, setChosen] = useState({ read: 0, index: 0 });
  const active = chosen.read === search.settled ? chosen.index : 0;
  const setActive = (index: number) =>
    setChosen({ read: search.settled, index });
  const { clear } = search;
  const results = search.results;

  const open = useCallback(() => {
    if (shown) return;
    opener.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    setQuery("");
    // Nothing from an earlier search shows, so the same words typed again read again.
    clear();
    setChosen({ read: -1, index: 0 });
    setShown(true);
  }, [clear, shown]);
  useShortcut(SEARCH_SHORTCUT.matches, open);

  function go(result: SearchResult | undefined): void {
    if (result === undefined) return;
    opener.current = null;
    setShown(false);
    router.push(result.href);
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>): void {
    // A key that ends an input method's composition isn't a command.
    if (event.nativeEvent.isComposing) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (results.length > 0) {
        setActive(moveActive(active, event.key, results.length));
      }
    } else if (event.key === "Enter") {
      event.preventDefault();
      // Only results for the words typed now open, never an older search's (WCMP-10).
      if (search.current) go(results[active]);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={open}
        aria-keyshortcuts={SEARCH_SHORTCUT.aria}
        data-field="search-button"
        className="text-sidebar-foreground/80 hover:bg-sidebar-accent border-sidebar-border flex w-full items-center gap-2 rounded-lg border px-2.5 py-1.5 text-ui"
      >
        <Search aria-hidden="true" className="size-3.5 shrink-0" />
        <span className="flex-1 text-left">Search</span>
        <kbd
          aria-hidden="true"
          className="text-muted-foreground border-sidebar-border rounded border px-1 font-mono text-kbd"
        >
          {SEARCH_SHORTCUT.keys.join("")}
        </kbd>
      </button>
      <Dialog
        open={shown}
        onClose={() => setShown(false)}
        initialFocus={input}
        // A chosen result clears the opener, so focus stays where the result's page puts it.
        returnFocus={() => opener.current}
        size="xl"
        placement="top"
        aria-label="Search"
        className="p-0"
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
            aria-expanded={results.length > 0}
            aria-controls={listId}
            aria-autocomplete="list"
            aria-activedescendant={
              results.length > 0 ? optionId(listId, active) : undefined
            }
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Search runs, Experts, workflows and tools"
            className="placeholder:text-muted-foreground h-auto min-w-0 flex-1 border-0 bg-transparent px-0 py-1 text-lead dark:bg-transparent"
          />
        </div>
        <SearchResults
          listId={listId}
          results={results}
          active={active}
          onHighlight={setActive}
          onOpen={go}
        />
        <SearchStatus search={search} />
      </Dialog>
    </>
  );
}
