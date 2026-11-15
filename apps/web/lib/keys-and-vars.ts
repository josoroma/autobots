/**
 * Settings → Keys & vars' words and fields (Decisions 0024 and 0025, PRD-Tool-Catalog PK-04 to
 * PK-08, WSYS-14). A value saved here wins over the environment and .env, for this workspace only.
 * A secret is never shown, only where it comes from. Tables are keyed by the contract's names, so an
 * item it gains fails the type check until it's described. Pure and JSX-free, so `node --test`
 * covers it.
 */
import type { KeyOrVar } from "@autobots/api-client";

import { refusalText } from "./submit.ts";

export type Name = KeyOrVar["name"];

export const TITLE: Readonly<Record<Name, string>> = {
  tavily: "Tavily",
  jina: "Jina",
  github_token: "GitHub token",
  github_repository: "GitHub repository",
  browser_executor: "Browsing",
};

export const USES: Readonly<Record<Name, string>> = {
  tavily: "Tavily Search, Tavily Extract, Tavily Map and Tavily Crawl",
  jina: "Search The Web and Extract Website Content",
  github_token:
    "The GitHub tools. A fine-grained token limited to the one repository",
  github_repository: "The one repository the GitHub tools use, as owner/name",
  browser_executor:
    "Browse goal, once the browser executor is qualified. Every call still waits for approval",
};

/** An item's control: an on and off choice, or a text field with an optional example. */
export type Field =
  { control: "toggle" } | { control: "text"; placeholder?: string };

export const FIELD: Readonly<Record<Name, Field>> = {
  tavily: { control: "text" },
  jina: { control: "text" },
  github_token: { control: "text" },
  github_repository: { control: "text", placeholder: "owner/name" },
  browser_executor: { control: "toggle" },
};

export function sourceLabel(item: KeyOrVar): string {
  const secret = item.kind === "secret";
  if (item.source === "settings") {
    return secret
      ? "Saved here for this workspace, encrypted on this Mac"
      : "Saved here for this workspace";
  }
  if (item.source === "environment") {
    return `${item.variable} from the server environment or .env`;
  }
  return secret
    ? "None. Its tools are unavailable"
    : `None. ${item.variable} isn't set`;
}

export function fieldLabel(item: KeyOrVar): string {
  if (item.kind !== "secret") return "Set for this workspace";
  return item.source === "settings" ? "Replace key" : "API key";
}

/** A toggle's saved choice. Anything but enabled reads as disabled. */
export function toggleValue(item: KeyOrVar): "enabled" | "disabled" {
  return item.value === "enabled" ? "enabled" : "disabled";
}

export const ITEM_SAVED = "Saved.";
export const ITEM_REMOVED = "Removed.";

// R-19 step 4: this screen's words for a refusal's code. Any other keeps the service's own, which
// are fixed per item and never echo what was submitted.
const REFUSALS: Readonly<Record<string, string>> = {
  not_signed_in:
    "Your session ended. Sign in, then try again. Nothing changed.",
  owner_required: "Only the workspace owner can save or remove one.",
};
const LOST =
  "The reply was lost, so this may have applied. What's shown is reloaded.";

/** What a save or removal says: `done` once accepted, else why in this screen's words. */
export function itemActionText(
  accepted: boolean,
  refusal: { code: string; message: string } | null,
  done: string,
): string {
  return accepted ? done : refusalText(REFUSALS, refusal, LOST);
}
