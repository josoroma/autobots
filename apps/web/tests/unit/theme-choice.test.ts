/**
 * The theme choice is kept outside React's context, so next-themes reading the Mac's colour scheme
 * after mount reaches only the appearance control, never a server-read section still waiting to
 * hydrate (R-67, lib/theme-choice.ts).
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  NO_CHOICE,
  publishThemeChoice,
  subscribeThemeChoice,
  themeChoice,
} from "../../lib/theme-choice.ts";

test("before next-themes reads it, there's no choice, as on the server", () => {
  assert.equal(themeChoice(), NO_CHOICE);
  assert.equal(themeChoice().theme, undefined);
});

test("a choice reaches each subscriber, and the snapshot stays the same object until the next", () => {
  const seen: (string | undefined)[] = [];
  const stop = subscribeThemeChoice(() => seen.push(themeChoice().theme));
  const setTheme = (): void => undefined;
  publishThemeChoice({ theme: "dark", setTheme });
  const snapshot = themeChoice();
  assert.equal(themeChoice(), snapshot);
  // The same choice again tells no one, so the control doesn't render for nothing.
  publishThemeChoice({ theme: "dark", setTheme });
  publishThemeChoice({ theme: "light", setTheme });
  assert.deepEqual(seen, ["dark", "light"]);
  stop();
  publishThemeChoice({ theme: "system", setTheme });
  assert.deepEqual(seen, ["dark", "light"]);
  assert.equal(themeChoice().theme, "system");
});
