import type { Search } from "@/components/search/use-search";
import { Button } from "@/components/ui/button";

/** The status line, announced as it changes, and Retry when a search failed for an outage. */
export function SearchStatus({ search }: { search: Search }) {
  return (
    <div className="border-border flex items-center gap-3 border-t px-4 py-2">
      <p
        role="status"
        data-field="search-status"
        data-reason={search.failure?.kind}
        className="text-muted-foreground flex-1 text-[12px]"
      >
        {search.status}
      </p>
      {search.retryable ? (
        <Button
          variant="outline"
          size="sm"
          disabled={search.pending}
          onClick={search.reload}
        >
          Retry
        </Button>
      ) : null}
    </div>
  );
}
