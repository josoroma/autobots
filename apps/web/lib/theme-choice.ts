/**
 * The theme a person chose and the way to change it, kept outside React's context (R-67).
 *
 * next-themes reads the Mac's colour scheme once it has mounted, and its context value changes when
 * that scheme differs from the stored or default theme. React passes any context change into each
 * Suspense boundary still waiting to hydrate, and a boundary whose streamed HTML is queued for its
 * reveal is then rendered again in the browser while React's hidden streamed copy stays in the page
 * until the reveal: every server-read section showed twice. So next-themes' provider wraps only the
 * bridge that copies its choice here, and the one control that needs it reads this store.
 * Browser-only state: on the server nothing publishes, so every request reads `NO_CHOICE`. Pure, so
 * `node --test` covers it.
 */

export interface ThemeChoice {
  /** The stored choice, such as "dark", "light" or "system", or undefined before next-themes reads it. */
  readonly theme: string | undefined;
  readonly setTheme: (theme: string) => void;
}

export const NO_CHOICE: ThemeChoice = {
  theme: undefined,
  setTheme: () => undefined,
};

const store: { current: ThemeChoice; listeners: Set<() => void> } = {
  current: NO_CHOICE,
  listeners: new Set(),
};

/** The newest choice. The same object until the next publish, as `useSyncExternalStore` needs. */
export function themeChoice(): ThemeChoice {
  return store.current;
}

/** Calls `listener` after each publish, until the returned function is called. */
export function subscribeThemeChoice(listener: () => void): () => void {
  store.listeners.add(listener);
  return () => {
    store.listeners.delete(listener);
  };
}

/** Records next-themes' choice and tells every subscriber. An equal choice changes nothing. */
export function publishThemeChoice(choice: ThemeChoice): void {
  const { theme, setTheme } = store.current;
  if (choice.theme === theme && choice.setTheme === setTheme) return;
  store.current = choice;
  store.listeners.forEach((listener) => listener());
}
