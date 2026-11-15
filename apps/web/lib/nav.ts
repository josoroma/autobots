/**
 * Which navigation link is current (PRD-Studio SH-01, WSHL-18). Pure and JSX-free, so `node --test`
 * covers it.
 */

/**
 * The longest link the path is at or under, so /settings/models marks Models and not Settings.
 * Home is current only on its own path.
 */
export function currentHref(
  pathname: string,
  hrefs: readonly string[],
): string | undefined {
  return hrefs
    .filter(
      (href) =>
        pathname === href || (href !== "/" && pathname.startsWith(`${href}/`)),
    )
    .sort((a, b) => b.length - a.length)[0];
}
