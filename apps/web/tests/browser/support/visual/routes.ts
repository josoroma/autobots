/**
 * The app's page routes, read from app/, so the visual walk can show that each one is a surface
 * or is listed as absent with its reason, and a new screen can't be skipped silently (TWEB-09).
 */
import { readdirSync } from "node:fs";
import { basename, dirname, sep } from "node:path";

/** Each page.tsx under `appDir` as its route, such as /runs/[id]. Route groups add no segment. */
export function pageRoutes(appDir: string): string[] {
  return readdirSync(appDir, { recursive: true, encoding: "utf8" })
    .filter((file) => basename(file) === "page.tsx")
    .map((file) => {
      const segments = dirname(file)
        .split(sep)
        .filter((segment) => segment !== "." && !/^\(.+\)$/.test(segment));
      return `/${segments.join("/")}`;
    })
    .sort();
}

/** Whether `path`, less any query, is an instance of `route`, whose [name] segments match any one. */
function opens(path: string, route: string): boolean {
  const pattern = route
    .split("/")
    .map((segment) =>
      /^\[.+\]$/.test(segment)
        ? "[^/]+"
        : segment.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"),
    )
    .join("/");
  return new RegExp(`^${pattern}$`).test(path.split("?")[0] ?? path);
}

/** The routes that none of `paths` opens and that `absent` doesn't list. */
export function unwalkedRoutes(
  routes: readonly string[],
  paths: readonly string[],
  absent: Readonly<Record<string, string>>,
): string[] {
  return routes.filter(
    (route) => !(route in absent) && !paths.some((path) => opens(path, route)),
  );
}
