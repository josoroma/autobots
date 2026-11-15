/**
 * The preferences this browser keeps, defined once (XWEB-18, WSHL-11, WSYS-11, XDUP-19): the theme's
 * storage key and choices (DS-02, Decision 0022 D2) and the presentation preferences of PRD-Studio
 * SE-03. The before-paint script in app/layout.tsx is built from this table, and the theme provider,
 * the Appearance control and the run page read it, so a key or value changes in one place. Pure, so
 * `node --test` covers it; nothing here holds a credential or touches a run.
 */

export const THEME_KEY = "autobots.theme";

/** The themes next-themes applies. System, which follows the OS, is its `enableSystem`. */
export const THEMES = ["dark", "light"] as const;

/** Every choice the theme's storage may hold. Any other value is removed before paint. */
export const THEME_CHOICES = [...THEMES, "system"] as const;

export type ThemeChoiceName = (typeof THEME_CHOICES)[number];

/** DS-02 as amended by Decision 0022 D2: dark for a first visit and any unusable stored value. */
export const DEFAULT_THEME: ThemeChoiceName = "dark";

/**
 * Each presentation preference: its value when nothing is stored, and the one other value, which
 * the page marks on the root element as `data-<name>` for globals.css and the run page to read.
 */
export const PRESENTATION = {
  serif: { fallback: "on", attribute: "off" },
  density: { fallback: "comfortable", attribute: "compact" },
  motion: { fallback: "system", attribute: "reduce" },
  stream: { fallback: "on", attribute: "off" },
} as const;

export type Preference = keyof typeof PRESENTATION;

export type PreferenceValue<P extends Preference> =
  (typeof PRESENTATION)[P]["fallback"] | (typeof PRESENTATION)[P]["attribute"];

/** Every preference, in the order the before-paint script marks them. */
export const PREFERENCES: readonly Preference[] = [
  "serif",
  "density",
  "motion",
  "stream",
];

export function storageKey(preference: Preference): string {
  return `autobots.${preference}`;
}

/** The storage a preference is kept in. A getter, since reaching `localStorage` itself can throw. */
export type StorageAccess = () => Pick<
  Storage,
  "getItem" | "setItem" | "removeItem"
>;

/** The root element's attributes, or a stand-in for one. */
export interface PreferenceRoot {
  dataset: DOMStringMap;
}

/**
 * The preference's value: the stored one when it is the other value, else the fallback. Storage that
 * can't be read gives what the page shows now, which the fallback or this session's choice set.
 */
export function readPreference<P extends Preference>(
  preference: P,
  storage: StorageAccess,
  root: PreferenceRoot,
): PreferenceValue<P> {
  const { fallback, attribute } = PRESENTATION[preference];
  try {
    return storage().getItem(storageKey(preference)) === attribute
      ? attribute
      : fallback;
  } catch {
    return root.dataset[preference] === attribute ? attribute : fallback;
  }
}

/**
 * Shows the value on the root element and stores it, removing the stored value for the fallback.
 * Storage that can't be written keeps the choice for this page only.
 */
export function applyPreference<P extends Preference>(
  preference: P,
  value: PreferenceValue<P>,
  storage: StorageAccess,
  root: PreferenceRoot,
): void {
  const { fallback, attribute } = PRESENTATION[preference];
  if (value === attribute) root.dataset[preference] = value;
  else delete root.dataset[preference];
  try {
    if (value === fallback) storage().removeItem(storageKey(preference));
    else storage().setItem(storageKey(preference), value);
  } catch {
    // Kept for this page only.
  }
}

/** US-15.24: whether the run page streams text as it's written, from the root's attribute. */
export function streamWanted(root: PreferenceRoot): boolean {
  return root.dataset.stream !== PRESENTATION.stream.attribute;
}

/**
 * The script that runs before paint (DS-02, SE-03). next-themes would apply any saved theme as a
 * class, so `garbage` would render the light tokens: this removes a stored theme that is not a
 * choice, and marks each presentation preference stored as its other value. Storage that can't be
 * read changes nothing, so the page stays dark and comfortable.
 */
export function beforePaintScript(): string {
  const text = (value: string) => JSON.stringify(value);
  const notChoice = THEME_CHOICES.map((choice) => `v!==${text(choice)}`).join(
    "&&",
  );
  const marks = PREFERENCES.map((preference) => {
    const value = text(PRESENTATION[preference].attribute);
    return `if(s.getItem(${text(storageKey(preference))})===${value})d.dataset.${preference}=${value}`;
  }).join(";");
  return `try{var s=localStorage,k=${text(THEME_KEY)},v=s.getItem(k);if(v!==null&&${notChoice})s.removeItem(k);var d=document.documentElement;${marks}}catch(e){}`;
}
